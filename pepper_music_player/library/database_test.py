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
                INSERT INTO AudioFile (file_id, token, album_token)
                VALUES (?, "b", "a")
                """,
                (file_id,),
            )
            self._connection.execute(
                """
                INSERT INTO AudioFileTag (file_id, tag_name, tag_value)
                VALUES (?, "c", "d")
                """,
                (file_id,),
            )
            self._connection.execute("""
                INSERT INTO AlbumTag (album_token, tag_name, tag_value)
                VALUES ("a", "c", "d")
            """)
        self._database.reset()
        with self._connection:
            for table_name in ('File', 'AudioFile', 'AudioFileTag', 'AlbumTag'):
                with self.subTest(table_name):
                    self.assertFalse(
                        self._connection.execute(
                            f'SELECT * FROM {table_name}').fetchall())

    def test_insert_files_generic(self):
        self._database.insert_files((
            metadata.File(dirname='a', filename='b'),
            metadata.AudioFile(dirname='c',
                               filename='d',
                               tags=metadata.Tags({})),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('a', 'b'),
                    ('c', 'd'),
                ),
                self._connection.execute('SELECT dirname, filename FROM File'),
            )

    def test_insert_files_duplicate(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._database.insert_files((
                metadata.File(dirname='a', filename='b'),
                metadata.File(dirname='a', filename='b'),
            ))
        with self._connection:
            self.assertFalse(
                self._connection.execute('SELECT * FROM File').fetchall())

    def test_insert_files_audio(self):
        file1 = metadata.AudioFile(dirname='a',
                                   filename='b',
                                   tags=metadata.Tags({'c': ('d',)}))
        file2 = metadata.AudioFile(dirname='a',
                                   filename='c',
                                   tags=metadata.Tags({
                                       'a': ('b', 'b'),
                                       'c': ('d',),
                                   }))
        self._database.insert_files((file1, file2))
        with self._connection:
            self.assertCountEqual(
                (
                    ('a', 'b', str(file1.token), str(file1.album_token)),
                    ('a', 'c', str(file2.token), str(file2.album_token)),
                ),
                self._connection.execute("""
                    SELECT dirname, filename, token, album_token
                    FROM File
                    JOIN AudioFile ON File.rowid = AudioFile.file_id
                """),
            )
            self.assertCountEqual(
                (
                    ('a', 'b', 'c', 'd'),
                    ('a', 'c', 'a', 'b'),
                    ('a', 'c', 'a', 'b'),
                    ('a', 'c', 'c', 'd'),
                ),
                self._connection.execute("""
                    SELECT dirname, filename, tag_name, tag_value
                    FROM File
                    JOIN AudioFileTag ON File.rowid = AudioFileTag.file_id
                """),
            )

    def test_insert_files_different_albums(self):
        self._database.insert_files((
            metadata.AudioFile(dirname='dir1',
                               filename='file1',
                               tags=metadata.Tags({'album': ('album1',)})),
            metadata.AudioFile(dirname='dir1',
                               filename='file2',
                               tags=metadata.Tags({'album': ('album2',)})),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('dir1', 'file1', 'album', 'album1'),
                    ('dir1', 'file2', 'album', 'album2'),
                ),
                self._connection.execute("""
                    SELECT dirname, filename, tag_name, tag_value
                    FROM File
                    JOIN AudioFile ON File.rowid = AudioFile.file_id
                    JOIN AlbumTag USING (album_token)
                """),
            )

    def test_insert_files_same_album(self):
        self._database.insert_files((
            metadata.AudioFile(dirname='dir1',
                               filename='file1',
                               tags=metadata.Tags({
                                   'album': ('album1',),
                                   'common': ('foo', 'foo'),
                                   'partially_common': ('common', 'diff1'),
                                   'different': ('diff1',),
                               })),
            metadata.AudioFile(dirname='dir1',
                               filename='file2',
                               tags=metadata.Tags({
                                   'album': ('album1',),
                                   'common': ('foo', 'foo'),
                                   'partially_common':
                                       ('common', 'common', 'diff2'),
                                   'different': ('diff2',),
                               })),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('dir1', 'file1', 'album', 'album1'),
                    ('dir1', 'file1', 'common', 'foo'),
                    ('dir1', 'file1', 'common', 'foo'),
                    ('dir1', 'file1', 'partially_common', 'common'),
                    ('dir1', 'file2', 'album', 'album1'),
                    ('dir1', 'file2', 'common', 'foo'),
                    ('dir1', 'file2', 'common', 'foo'),
                    ('dir1', 'file2', 'partially_common', 'common'),
                ),
                self._connection.execute("""
                    SELECT dirname, filename, tag_name, tag_value
                    FROM File
                    JOIN AudioFile ON File.rowid = AudioFile.file_id
                    JOIN AlbumTag USING (album_token)
                """),
            )

    def test_insert_files_album_with_no_common_tags(self):
        self._database.insert_files((
            metadata.AudioFile(dirname='dir1',
                               filename='file1',
                               tags=metadata.Tags({})),
            metadata.AudioFile(dirname='dir1',
                               filename='file2',
                               tags=metadata.Tags({'foo': ('bar',)})),
        ))
        with self._connection:
            self.assertFalse(
                self._connection.execute('SELECT * FROM AlbumTag').fetchall())

    def test_track_tokens(self):
        file1 = metadata.AudioFile(dirname='a',
                                   filename='b',
                                   tags=metadata.Tags({}))
        file2 = metadata.AudioFile(dirname='a',
                                   filename='c',
                                   tags=metadata.Tags({}))
        self._database.insert_files((file1, file2))
        self.assertCountEqual((file1.token, file2.token),
                              self._database.track_tokens())

    def test_track_not_found(self):
        with self.assertRaises(KeyError):
            self._database.track(metadata.TrackToken('foo'))

    def test_track(self):
        track = metadata.AudioFile(dirname='a',
                                   filename='b',
                                   tags=metadata.Tags({
                                       'c': ('foo', 'bar'),
                                       'd': ('quux',),
                                   }))
        self._database.insert_files((track,))
        self.assertEqual(track, self._database.track(track.token))


if __name__ == '__main__':
    unittest.main()
