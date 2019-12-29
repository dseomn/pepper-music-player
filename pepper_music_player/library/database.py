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

import sqlite3
import threading
from typing import Iterable

from pepper_music_player.library import scan

_SCHEMA_DROP = (
    'DROP TABLE IF EXISTS File',
    'DROP TABLE IF EXISTS AudioFileTag',
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

    # Tags for audio files in the library.
    #
    # Columns:
    #   file_id: Which file has the tag.
    #   tag_name: Name of the tag, e.g., 'artist'. Each value may appear
    #     multiple times for the same file_id.
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
)


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
    # https://docs.python.org/3.8/library/sqlite3.html#multithreading says that
    # sqlite3 connections shouldn't be shared between threads.
    if not hasattr(self._local, 'connection'):
      self._local.connection = sqlite3.connect(
          self._sqlite3_path, isolation_level=None)
    return self._local.connection

  def reset(self) -> None:
    """(Re)sets the database to its initial, empty state."""
    with self._connection:
      for statement in _SCHEMA_DROP + _SCHEMA_CREATE:
        self._connection.execute(statement)

  def insert_files(self, files: Iterable[scan.File]) -> None:
    """Inserts information about the given files.

    Args:
      files: Files to insert into the database.

    Raises:
      sqlite3.IntegrityError: One or more files are already in the database.
    """
    with self._connection:
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
        if isinstance(file_info, scan.AudioFile):
          self._connection.executemany(
              """
              INSERT INTO AudioFileTag (file_id, tag_name, tag_value)
              VALUES (:file_id, :tag_name, :tag_value)
              """,
              (dict(file_id=file_id, tag_name=tag_name, tag_value=tag_value)
               for tag_name, tag_value in file_info.tags),
          )
