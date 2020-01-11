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
from pepper_music_player.library import scan
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
            scan.File(dirname='a', basename='b'),
            scan.AudioFile(
                dirname='c',
                basename='d',
                track=entity.Track(tags=tag.Tags({tag.FILENAME: ('c/d',)}))),
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
                scan.File(dirname='a', basename='b'),
                scan.File(dirname='a', basename='b'),
            ))
        with self._connection:
            self.assertFalse(
                self._connection.execute('SELECT * FROM File').fetchall())

    def test_insert_files_audio(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('a/b',),
            'c': ('d',),
        }))
        track2 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('a/c',),
            'a': ('b', 'b'),
            'c': ('d',),
        }))
        self._database.insert_files((
            scan.AudioFile(dirname='a', basename='b', track=track1),
            scan.AudioFile(dirname='a', basename='c', track=track2),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('a', 'b', str(track1.token), str(track1.album_token)),
                    ('a', 'c', str(track2.token), str(track2.album_token)),
                ),
                self._connection.execute("""
                    SELECT dirname, basename, token, album_token
                    FROM File
                    JOIN AudioFile ON File.rowid = AudioFile.file_id
                """),
            )
            self.assertCountEqual(
                (
                    ('a', 'b', '~filename', 'a/b'),
                    ('a', 'b', 'c', 'd'),
                    ('a', 'c', '~filename', 'a/c'),
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
            scan.AudioFile(dirname='dir1',
                           basename='file1',
                           track=entity.Track(tags=tag.Tags({
                               tag.FILENAME: ('dir1/file1',),
                               'album': ('album1',),
                           }))),
            scan.AudioFile(dirname='dir1',
                           basename='file2',
                           track=entity.Track(tags=tag.Tags({
                               tag.FILENAME: ('dir1/file2',),
                               'album': ('album2',),
                           }))),
        ))
        with self._connection:
            self.assertCountEqual(
                (
                    ('dir1', 'file1', '~filename', 'dir1/file1'),
                    ('dir1', 'file1', 'album', 'album1'),
                    ('dir1', 'file2', '~filename', 'dir1/file2'),
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
            scan.AudioFile(dirname='dir1',
                           basename='file1',
                           track=entity.Track(tags=tag.Tags({
                               tag.FILENAME: ('dir1/file1',),
                               'album': ('album1',),
                               'partially_common': ('common', 'diff1'),
                           }))),
            scan.AudioFile(dirname='dir1',
                           basename='file2',
                           track=entity.Track(tags=tag.Tags({
                               tag.FILENAME: ('dir1/file2',),
                               'album': ('album1',),
                               'partially_common': ('common', 'common',
                                                    'diff2'),
                           }))),
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
        track1 = entity.Track(tags=tag.Tags({tag.FILENAME: ('a/b',)}))
        track2 = entity.Track(tags=tag.Tags({tag.FILENAME: ('a/c',)}))
        self._database.insert_files((
            scan.AudioFile(dirname='a', basename='b', track=track1),
            scan.AudioFile(dirname='a', basename='c', track=track2),
        ))
        self.assertCountEqual((track1.token, track2.token),
                              self._database.track_tokens())

    def test_track_not_found(self):
        with self.assertRaises(KeyError):
            self._database.track(token.Track('foo'))

    def test_track(self):
        track = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('a/b',),
            'c': ('foo', 'bar'),
            'd': ('quux',),
        }))
        self._database.insert_files((scan.AudioFile(dirname='a',
                                                    basename='b',
                                                    track=track),))
        self.assertEqual(track, self._database.track(track.token))


if __name__ == '__main__':
    unittest.main()
