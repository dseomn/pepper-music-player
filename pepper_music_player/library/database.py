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
import functools
import itertools
import operator
from typing import Generator, Iterable, Tuple

from pepper_music_player import metadata
from pepper_music_player import sqlite3_db

_SCHEMA = sqlite3_db.Schema(
    name='library',
    version='v1alpha',  # TODO(#20): Change to v1.
    items=(
        # Files in the library.
        #
        # Columns:
        #   dirname: Absolute name of the directory containing the file.
        #   filename: Name of the file, relative to dirname.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE File (
                dirname TEXT NOT NULL,
                filename TEXT NOT NULL,
                PRIMARY KEY (dirname, filename)
            )
            """,
            drop='DROP TABLE IF EXISTS File',
        ),

        # Audio files in the library.
        #
        # See note in metadata.AudioFile's docstring about the conflation of audio
        # files and tracks.
        #
        # Columns:
        #   file_id: Which file it is.
        #   token: Opaque token that identifies this track.
        #   album_token: Opaque token that identifies the album the file is on.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE AudioFile (
                file_id INTEGER NOT NULL
                    REFERENCES File (rowid) ON DELETE CASCADE,
                token TEXT NOT NULL,
                album_token TEXT NOT NULL,
                PRIMARY KEY (file_id),
                UNIQUE (token)
            )
            """,
            drop='DROP TABLE IF EXISTS AudioFile',
        ),
        sqlite3_db.SchemaItem(
            'CREATE INDEX AudioFile_AlbumIndex ON AudioFile (album_token)'),

        # Tags for audio files in the library.
        #
        # Columns:
        #   file_id: Which file has the tag.
        #   tag_name: Name of the tag, e.g., 'artist'. Each value may appear
        #       multiple times for the same file_id.
        #   tag_value: A single value for the tag.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE AudioFileTag (
                file_id INTEGER NOT NULL
                    REFERENCES File (rowid) ON DELETE CASCADE,
                tag_name TEXT NOT NULL,
                tag_value TEXT NOT NULL
            )
            """,
            drop='DROP TABLE IF EXISTS AudioFileTag',
        ),
        sqlite3_db.SchemaItem(
            'CREATE INDEX AudioFileTag_FileIndex ON AudioFileTag (file_id)'),
        sqlite3_db.SchemaItem("""
            CREATE INDEX AudioFileTag_TagIndex
            ON AudioFileTag (tag_name, tag_value)
        """),

        # Tags common to all tracks on an Album.
        #
        # Columns:
        #   album_token: Opaque token that identifies the album.
        #   tag_name: See AudioFileTag.
        #   tag_value: See AudioFileTag.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE AlbumTag (
                album_token TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                tag_value TEXT NOT NULL
            )
            """,
            drop='DROP TABLE IF EXISTS AlbumTag',
        ),
        sqlite3_db.SchemaItem(
            'CREATE INDEX AlbumTag_AlbumIndex ON AlbumTag (album_token)'),
        sqlite3_db.SchemaItem(
            'CREATE INDEX AlbumTag_TagIndex ON AlbumTag (tag_name, tag_value)'),
    ),
)


def _tags_from_pairs(pairs: Iterable[Tuple[str, str]]) -> metadata.Tags:
    """Returns Tags, given an iterable of (name, value) pairs."""
    tags = collections.defaultdict(list)
    for name, value in pairs:
        tags[name].append(value)
    return metadata.Tags(tags)


class Database:
    """Database for a library."""

    def __init__(
            self,
            *,
            database_dir: str,
    ) -> None:
        """Initializer.

        Args:
            database_dir: Directory containing databases.
        """
        self._db = sqlite3_db.Database(_SCHEMA, database_dir=database_dir)

    def reset(self) -> None:
        """(Re)sets the library to its initial, empty state."""
        self._db.reset()

    def _insert_audio_file(
            self,
            transaction: sqlite3_db.Transaction,
            file_id: int,
            file_info: metadata.AudioFile,
    ) -> None:
        """Inserts information about the given audio file.

        Args:
            transaction: Transaction to use.
            file_id: Row ID of the file in the File table.
            file_info: File to insert.
        """
        transaction.execute(
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
            transaction.executemany(
                """
                INSERT INTO AudioFileTag (file_id, tag_name, tag_value)
                VALUES (?, ?, ?)
                """,
                ((file_id, tag_name, tag_value) for tag_value in tag_values),
            )

    def _update_album_tags(self, transaction: sqlite3_db.Transaction) -> None:
        """Updates the AlbumTag table to reflect the current files."""
        transaction.execute('DELETE FROM AlbumTag')
        for album_token, audio_file_rows in itertools.groupby(
                transaction.execute("""
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
            transaction.executemany(
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
        with self._db.transaction() as transaction:
            for file_info in files:
                file_id = transaction.execute(
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
                    self._insert_audio_file(transaction, file_id, file_info)
            self._update_album_tags(transaction)

    def track_tokens(self) -> Generator[metadata.TrackToken, None, None]:
        """Yields all track tokens."""
        with self._db.snapshot() as snapshot:
            for (token_str,) in (
                    snapshot.execute('SELECT token FROM AudioFile')):
                yield metadata.TrackToken(token_str)

    def track(self, token: metadata.TrackToken) -> metadata.AudioFile:
        """Returns the specified track.

        Args:
            token: Which track to return.

        Raises:
            KeyError: There's no track with the given token.
        """
        with self._db.snapshot() as snapshot:
            track_row = snapshot.execute(
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
                    snapshot.execute(
                        """
                        SELECT tag_name, tag_value
                        FROM AudioFileTag
                        WHERE file_id = ?
                        """,
                        (file_id,),
                    )),
            )
