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
"""Tests for pepper_music_player.library.database."""

import os
import sqlite3
import tempfile
import unittest

from pepper_music_player.library import database
from pepper_music_player import metadata


class DatabaseTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        sqlite3_path = os.path.join(tempdir.name, 'database.sqlite3')
        self._database = database.Database(sqlite3_path)
        self._database.reset()
        self._connection = sqlite3.connect(sqlite3_path, isolation_level=None)

    def test_reset_deletes_data(self):
        with self._connection:
            file_id = self._connection.execute(
                'INSERT INTO File (dirname, filename) VALUES ("a", "b")'
            ).lastrowid
            self._connection.execute(
                """
                INSERT INTO AudioFileTag (file_id, tag_name, tag_value)
                VALUES (?, "c", "d")
                """,
                (file_id,),
            )
        self._database.reset()
        with self._connection:
            self.assertFalse(
                self._connection.execute('SELECT * FROM File').fetchall())
            self.assertFalse(
                self._connection.execute(
                    'SELECT * FROM AudioFileTag').fetchall())

    def test_insert_files_generic(self):
        self._database.insert_files((
            metadata.File(dirname='a', filename='b'),
            metadata.AudioFile(dirname='c',
                               filename='d',
                               tags=metadata.Tags({})),
        ))
        with self._connection:
            self.assertEqual(
                {
                    ('a', 'b'),
                    ('c', 'd'),
                },
                frozenset(
                    self._connection.execute(
                        'SELECT dirname, filename FROM File')),
            )

    def test_insert_files_duplicate(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._database.insert_files((
                metadata.File(dirname='a', filename='b'),
                metadata.File(dirname='a', filename='b'),
            ))

    def test_insert_files_audio(self):
        self._database.insert_files((
            metadata.AudioFile(dirname='a',
                               filename='b',
                               tags=metadata.Tags({'c': ('d',)})),
            metadata.AudioFile(dirname='a',
                               filename='c',
                               tags=metadata.Tags({
                                   'a': ('b', 'b'),
                                   'c': ('d',),
                               })),
        ))
        with self._connection:
            self.assertEqual(
                {
                    ('a', 'b', 'c', 'd'),
                    ('a', 'c', 'a', 'b'),
                    ('a', 'c', 'a', 'b'),
                    ('a', 'c', 'c', 'd'),
                },
                frozenset(
                    self._connection.execute(
                        """
                        SELECT dirname, filename, tag_name, tag_value
                        FROM File
                        JOIN AudioFileTag ON File.rowid = AudioFileTag.file_id
                        """,)),
            )


if __name__ == '__main__':
    unittest.main()
