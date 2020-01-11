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
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token


class DatabaseTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._database = database.Database(database_dir=tempdir.name)
        self._database.reset()
        # TODO(dseomn): Change tests to use only public methods of
        # self._database instead of inspecting the underlying database, then
        # delete this connection.
        self._connection = sqlite3.connect(
            os.path.join(tempdir.name, 'library.v1alpha.sqlite3'),
            isolation_level=None,
        )

    def test_reset_deletes_data(self):
        with self._connection:
            self._connection.execute("""
                INSERT INTO Tag (token, tag_name, tag_value)
                VALUES ("b", "c", "d")
            """)
            file_id = self._connection.execute(
                'INSERT INTO File (dirname, basename) VALUES ("a", "b")'
            ).lastrowid
            self._connection.execute(
                """
                INSERT INTO AudioFile (file_id, token, album_token)
                VALUES (?, "b", "a")
                """,
                (file_id,),
            )
        self._database.reset()
        with self._connection:
            for table_name in ('Tag', 'File', 'AudioFile'):
                with self.subTest(table_name):
                    self.assertFalse(
                        self._connection.execute(
                            f'SELECT * FROM {table_name}').fetchall())

    def test_insert_files_generic(self):
        self._database.insert_files((
            entity.File(dirname='a', basename='b'),
            entity.AudioFile(dirname='c', basename='d', tags=tag.Tags({})),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('a', 'b'),
                    ('c', 'd'),
                ),
                self._connection.execute('SELECT dirname, basename FROM File'),
            )

    def test_insert_files_duplicate(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._database.insert_files((
                entity.File(dirname='a', basename='b'),
                entity.File(dirname='a', basename='b'),
            ))
        with self._connection:
            self.assertFalse(
                self._connection.execute('SELECT * FROM File').fetchall())

    def test_insert_files_audio(self):
        file1 = entity.AudioFile(dirname='a',
                                 basename='b',
                                 tags=tag.Tags({'c': ('d',)}))
        file2 = entity.AudioFile(dirname='a',
                                 basename='c',
                                 tags=tag.Tags({
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
                    SELECT dirname, basename, token, album_token
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
                    SELECT dirname, basename, tag_name, tag_value
                    FROM File
                    JOIN AudioFile ON AudioFile.file_id = File.rowid
                    JOIN Tag USING (token)
                """),
            )

    def test_insert_files_different_albums(self):
        self._database.insert_files((
            entity.AudioFile(dirname='dir1',
                             basename='file1',
                             tags=tag.Tags({'album': ('album1',)})),
            entity.AudioFile(dirname='dir1',
                             basename='file2',
                             tags=tag.Tags({'album': ('album2',)})),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('dir1', 'file1', 'album', 'album1'),
                    ('dir1', 'file2', 'album', 'album2'),
                ),
                self._connection.execute("""
                    SELECT dirname, basename, tag_name, tag_value
                    FROM File
                    JOIN AudioFile ON File.rowid = AudioFile.file_id
                    JOIN Tag ON Tag.token = AudioFile.album_token
                """),
            )

    def test_insert_files_same_album(self):
        self._database.insert_files((
            entity.AudioFile(dirname='dir1',
                             basename='file1',
                             tags=tag.Tags({
                                 'album': ('album1',),
                                 'partially_common': ('common', 'diff1'),
                             })),
            entity.AudioFile(dirname='dir1',
                             basename='file2',
                             tags=tag.Tags({
                                 'album': ('album1',),
                                 'partially_common':
                                     ('common', 'common', 'diff2'),
                             })),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('dir1', 'file1', 'album', 'album1'),
                    ('dir1', 'file1', 'partially_common', 'common'),
                    ('dir1', 'file2', 'album', 'album1'),
                    ('dir1', 'file2', 'partially_common', 'common'),
                ),
                self._connection.execute("""
                    SELECT dirname, basename, tag_name, tag_value
                    FROM File
                    JOIN AudioFile ON File.rowid = AudioFile.file_id
                    JOIN Tag ON Tag.token = AudioFile.album_token
                """),
            )

    def test_track_tokens(self):
        file1 = entity.AudioFile(dirname='a', basename='b', tags=tag.Tags({}))
        file2 = entity.AudioFile(dirname='a', basename='c', tags=tag.Tags({}))
        self._database.insert_files((file1, file2))
        self.assertCountEqual((file1.token, file2.token),
                              self._database.track_tokens())

    def test_track_not_found(self):
        with self.assertRaises(KeyError):
            self._database.track(token.Track('foo'))

    def test_track(self):
        track = entity.AudioFile(dirname='a',
                                 basename='b',
                                 tags=tag.Tags({
                                     'c': ('foo', 'bar'),
                                     'd': ('quux',),
                                 }))
        self._database.insert_files((track,))
        self.assertEqual(track, self._database.track(track.token))


if __name__ == '__main__':
    unittest.main()
