# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Database for a library."""

import collections
import contextlib
import functools
import itertools
import operator
import sqlite3
import threading
from typing import Generator, Iterable, Tuple

from pepper_music_player import metadata

_SCHEMA_DROP = (
    'DROP TABLE IF EXISTS File',
    'DROP TABLE IF EXISTS AudioFile',
    'DROP TABLE IF EXISTS AudioFileTag',
    'DROP TABLE IF EXISTS AlbumTag',
)

_SCHEMA_CREATE = (
    # Files in the library.
    #
    # Columns:
    #   dirname: Absolute name of the directory containing the file.
    #   filename: Name of the file, relative to dirname.
    """
    CREATE TABLE File (
        dirname TEXT NOT NULL,
        filename TEXT NOT NULL,
        PRIMARY KEY (dirname, filename)
    )
    """,

    # Audio files in the library.
    #
    # See note in metadata.AudioFile's docstring about the conflation of audio
    # files and tracks.
    #
    # Columns:
    #   file_id: Which file it is.
    #   token: Opaque token that identifies this track.
    #   album_token: Opaque token that identifies the album the file is on.
    """
    CREATE TABLE AudioFile (
        file_id INTEGER NOT NULL REFERENCES File (rowid) ON DELETE CASCADE,
        token TEXT NOT NULL,
        album_token TEXT NOT NULL,
        PRIMARY KEY (file_id),
        UNIQUE (token)
    )
    """,
    'CREATE INDEX AudioFile_AlbumIndex ON AudioFile (album_token)',

    # Tags for audio files in the library.
    #
    # Columns:
    #   file_id: Which file has the tag.
    #   tag_name: Name of the tag, e.g., 'artist'. Each value may appear
    #       multiple times for the same file_id.
    #   tag_value: A single value for the tag.
    """
    CREATE TABLE AudioFileTag (
        file_id INTEGER NOT NULL REFERENCES File (rowid) ON DELETE CASCADE,
        tag_name TEXT NOT NULL,
        tag_value TEXT NOT NULL
    )
    """,
    'CREATE INDEX AudioFileTag_FileIndex ON AudioFileTag (file_id)',
    'CREATE INDEX AudioFileTag_TagIndex ON AudioFileTag (tag_name, tag_value)',

    # Tags common to all tracks on an Album.
    #
    # Columns:
    #   album_token: Opaque token that identifies the album.
    #   tag_name: See AudioFileTag.
    #   tag_value: See AudioFileTag.
    """
    CREATE TABLE AlbumTag (
        album_token TEXT NOT NULL,
        tag_name TEXT NOT NULL,
        tag_value TEXT NOT NULL
    )
    """,
    'CREATE INDEX AlbumTag_AlbumIndex ON AlbumTag (album_token)',
    'CREATE INDEX AlbumTag_TagIndex ON AlbumTag (tag_name, tag_value)',
)


def _tags_from_pairs(pairs: Iterable[Tuple[str, str]]) -> metadata.Tags:
    """Returns Tags, given an iterable of (name, value) pairs."""
    tags = collections.defaultdict(list)
    for name, value in pairs:
        tags[name].append(value)
    return metadata.Tags(tags)


class Database:
    """Database for a library."""

    def __init__(self, sqlite3_path: str) -> None:
        """Initializer.

        Args:
            sqlite3_path: Path to a sqlite3 database.
        """
        self._sqlite3_path = sqlite3_path
        self._local = threading.local()

    @property
    def _connection(self) -> sqlite3.Connection:
        # https://docs.python.org/3.8/library/sqlite3.html#multithreading says
        # that sqlite3 connections shouldn't be shared between threads.
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self._sqlite3_path,
                                                     isolation_level=None)
            self._local.connection.execute('PRAGMA journal_mode=WAL')
        return self._local.connection

    @contextlib.contextmanager
    def _transaction(self) -> Generator[None, None, None]:
        """Returns a context manager around a transaction.

        This behaves like the connection context manager is supposed to, but
        works with isolation_level=None. For more context, see:

        https://docs.python.org/3/library/sqlite3.html#using-the-connection-as-a-context-manager

        https://bugs.python.org/issue16958
        """
        # TODO(https://bugs.python.org/issue16958): Delete this method.
        self._connection.execute('BEGIN TRANSACTION')
        try:
            yield
        except:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()

    def reset(self) -> None:
        """(Re)sets the database to its initial, empty state."""
        with self._transaction():
            for statement in _SCHEMA_DROP + _SCHEMA_CREATE:
                self._connection.execute(statement)

    def _insert_audio_file(
            self,
            file_id: int,
            file_info: metadata.AudioFile,
    ) -> None:
        """Inserts information about the given audio file.

        The caller is responsible for managing the transaction around this
        function.

        Args:
            file_id: Row ID of the file in the File table.
            file_info: File to insert.
        """
        self._connection.execute(
            """
            INSERT INTO AudioFile (file_id, token, album_token)
            VALUES (:file_id, :token, :album_token)
            """,
            {
                'file_id': file_id,
                'token': str(file_info.token),
                'album_token': str(file_info.album_token),
            },
        )
        for tag_name, tag_values in file_info.tags.items():
            self._connection.executemany(
                """
                INSERT INTO AudioFileTag (file_id, tag_name, tag_value)
                VALUES (?, ?, ?)
                """,
                ((file_id, tag_name, tag_value) for tag_value in tag_values),
            )

    def _update_album_tags(self) -> None:
        """Updates the AlbumTag table to reflect the current files.

        The caller is responsible for managing the transaction around this
        function.
        """
        self._connection.execute('DELETE FROM AlbumTag')
        for album_token, audio_file_rows in itertools.groupby(
                self._connection.execute("""
                    SELECT album_token, file_id, tag_name, tag_value
                    FROM AudioFile
                    LEFT JOIN AudioFileTag USING (file_id)
                    ORDER BY album_token, file_id
                """),
                lambda row: row[0],
        ):
            tags = []
            for file_id, tag_rows in itertools.groupby(audio_file_rows,
                                                       lambda row: row[1]):
                tags.append(
                    collections.Counter(
                        (tag_name, tag_value)
                        for _, _, tag_name, tag_value in tag_rows
                        if tag_name is not None))
            common_tags = functools.reduce(operator.and_, tags)
            self._connection.executemany(
                """
                INSERT INTO AlbumTag (album_token, tag_name, tag_value)
                VALUES (?, ?, ?)
                """,
                ((album_token, tag_name, tag_value)
                 for tag_name, tag_value in common_tags.elements()),
            )

    def insert_files(self, files: Iterable[metadata.File]) -> None:
        """Inserts information about the given files.

        Args:
            files: Files to insert into the database.

        Raises:
            sqlite3.IntegrityError: One or more files are already in the
                database.
        """
        with self._transaction():
            for file_info in files:
                file_id = self._connection.execute(
                    """
                    INSERT INTO File (dirname, filename)
                    VALUES (:dirname, :filename)
                    """,
                    {
                        'dirname': file_info.dirname,
                        'filename': file_info.filename,
                    },
                ).lastrowid
                if isinstance(file_info, metadata.AudioFile):
                    self._insert_audio_file(file_id, file_info)
            self._update_album_tags()

    def track_tokens(self) -> Generator[metadata.TrackToken, None, None]:
        """Yields all track tokens."""
        with self._transaction():
            for (token_str,) in (
                    self._connection.execute('SELECT token FROM AudioFile')):
                yield metadata.TrackToken(token_str)

    def track(self, token: metadata.TrackToken) -> metadata.AudioFile:
        """Returns the specified track.

        Args:
            token: Which track to return.

        Raises:
            KeyError: There's no track with the given token.
        """
        with self._transaction():
            track_row = self._connection.execute(
                """
                SELECT dirname, filename, file_id
                FROM AudioFile
                JOIN File ON File.rowid = AudioFile.file_id
                WHERE token = ?
                """,
                (str(token),),
            ).fetchone()
            if track_row is None:
                raise KeyError(token)
            dirname, filename, file_id = track_row
            return metadata.AudioFile(
                dirname=dirname,
                filename=filename,
                tags=_tags_from_pairs(
                    self._connection.execute(
                        """
                        SELECT tag_name, tag_value
                        FROM AudioFileTag
                        WHERE file_id = ?
                        """,
                        (file_id,),
                    )),
            )
