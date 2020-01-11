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
import itertools
from typing import Generator, Iterable

from pepper_music_player import metadata
from pepper_music_player import sqlite3_db

_SCHEMA = sqlite3_db.Schema(
    name='library',
    version='v1alpha',  # TODO(#20): Change to v1.
    items=(
        # Tags for anything in the library.
        #
        # Columns:
        #   token: Token of the thing (track, album, etc.) with tags.
        #   tag_name: Name of the tag, e.g., 'artist'. Each value may appear
        #       multiple times for the same token.
        #   tag_value: A single value for the tag.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE Tag (
                token TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                tag_value TEXT NOT NULL
            )
            """,
            drop='DROP TABLE IF EXISTS Tag',
        ),
        sqlite3_db.SchemaItem('CREATE INDEX Tag_TokenIndex ON Tag (token)'),
        sqlite3_db.SchemaItem(
            'CREATE INDEX Tag_TagIndex ON Tag (tag_name, tag_value)'),

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
    ),
)


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

    def _get_tags(
            self,
            snapshot: sqlite3_db.AbstractSnapshot,
            token: str,
    ) -> metadata.Tags:
        """Returns Tags for the given token."""
        tags = collections.defaultdict(list)
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for name, value in snapshot.execute(
                'SELECT tag_name, tag_value FROM Tag WHERE token = ?',
                (token,)):  # yapf: disable
            tags[name].append(value)
        return metadata.Tags(tags)

    def _set_tags(
            self,
            transaction: sqlite3_db.Transaction,
            token: str,
            tags: metadata.Tags,
    ) -> None:
        """Sets Tags for the given token."""
        transaction.execute('DELETE FROM Tag WHERE token = ?', (token,))
        for name, values in tags.items():
            transaction.executemany(
                'INSERT INTO Tag (token, tag_name, tag_value) VALUES (?, ?, ?)',
                ((token, name, value) for value in values),
            )

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
        token = str(file_info.token)
        transaction.execute(
            """
            INSERT INTO AudioFile (file_id, token, album_token)
            VALUES (:file_id, :token, :album_token)
            """,
            {
                'file_id': file_id,
                'token': token,
                'album_token': str(file_info.album_token),
            },
        )
        self._set_tags(transaction, token, file_info.tags)

    def _update_album_tags(self, transaction: sqlite3_db.Transaction) -> None:
        """Updates album tags to reflect the current files."""
        for album_token, rows in itertools.groupby(
                transaction.execute("""
                    SELECT album_token, token
                    FROM AudioFile
                    ORDER BY album_token
                """),
                lambda row: row[0],
        ):
            self._set_tags(
                transaction,
                album_token,
                metadata.compose_tags(
                    self._get_tags(transaction, track_token)
                    for _, track_token in rows),
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
                SELECT dirname, filename
                FROM AudioFile
                JOIN File ON File.rowid = AudioFile.file_id
                WHERE token = ?
                """,
                (str(token),),
            ).fetchone()
            if track_row is None:
                raise KeyError(token)
            dirname, filename = track_row
            return metadata.AudioFile(dirname=dirname,
                                      filename=filename,
                                      tags=self._get_tags(snapshot, str(token)))
