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

    def test_reset_deletes_data(self):
        self._database.insert_files((scan.AudioFile(
            filename='/a/b',
            dirname='/a',
            basename='b',
            track=entity.Track(tags=tag.Tags({tag.FILENAME: ('/a/b',)}))),))
        self._database.reset()
        self.assertFalse(self._database.search())

    def test_insert_files_generic(self):
        self._database.insert_files((scan.File(filename='/a/b',
                                               dirname='/a',
                                               basename='b'),))
        self.assertFalse(self._database.search())

    def test_insert_files_duplicate(self):
        file1 = scan.AudioFile(
            filename='/a/b',
            dirname='/a',
            basename='b',
            track=entity.Track(tags=tag.Tags({tag.FILENAME: ('/a/b',)})))
        with self.assertRaises(sqlite3.IntegrityError):
            self._database.insert_files((file1, file1))
        self.assertFalse(self._database.search())

    def test_insert_files_audio(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/a/b',),
            'c': ('d',),
        }))
        track2 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/a/c',),
            'a': ('b', 'b'),
            'c': ('d',),
        }))
        self._database.insert_files((
            scan.AudioFile(filename='/a/b',
                           dirname='/a',
                           basename='b',
                           track=track1),
            scan.AudioFile(filename='/a/c',
                           dirname='/a',
                           basename='c',
                           track=track2),
        ))
        self.assertCountEqual((track1.token, track2.token),
                              (token_ for token_ in self._database.search()
                               if isinstance(token_, token.Track)))
        self.assertEqual(track1, self._database.track(track1.token))
        self.assertEqual(track2, self._database.track(track2.token))

    def test_insert_files_different_albums(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file1',),
            'album': ('album1',),
        }))
        medium1 = entity.Medium(tags=track1.tags, tracks=(track1,))
        album1 = entity.Album(tags=track1.tags, mediums=(medium1,))
        track2 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file2',),
            'album': ('album2',),
        }))
        medium2 = entity.Medium(tags=track2.tags, tracks=(track2,))
        album2 = entity.Album(tags=track2.tags, mediums=(medium2,))
        self._database.insert_files((
            scan.AudioFile(filename='/dir1/file1',
                           dirname='/dir1',
                           basename='file1',
                           track=track1),
            scan.AudioFile(filename='/dir1/file2',
                           dirname='/dir1',
                           basename='file2',
                           track=track2),
        ))
        self.assertCountEqual((track1.medium_token, track2.medium_token),
                              (token_ for token_ in self._database.search()
                               if isinstance(token_, token.Medium)))
        self.assertEqual(medium1, self._database.medium(track1.medium_token))
        self.assertEqual(medium2, self._database.medium(track2.medium_token))
        self.assertCountEqual((track1.album_token, track2.album_token),
                              (token_ for token_ in self._database.search()
                               if isinstance(token_, token.Album)))
        self.assertEqual(album1, self._database.album(track1.album_token))
        self.assertEqual(album2, self._database.album(track2.album_token))

    def test_insert_files_same_album(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file1',),
            'album': ('album1',),
            'tracknumber': ('1',),
            'partially_common': ('common', 'diff1'),
        }).derive())
        track2 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file2',),
            'album': ('album1',),
            'tracknumber': ('2',),
            'partially_common': ('common', 'common', 'diff2'),
        }).derive())
        medium = entity.Medium(
            tags=tag.Tags({
                'album': ('album1',),
                'partially_common': ('common',),
            }),
            tracks=(track1, track2),
        )
        album = entity.Album(tags=medium.tags, mediums=(medium,))
        self._database.insert_files((
            scan.AudioFile(filename='/dir1/file1',
                           dirname='/dir1',
                           basename='file1',
                           track=track1),
            scan.AudioFile(filename='/dir1/file2',
                           dirname='/dir1',
                           basename='file2',
                           track=track2),
        ))
        self.assertCountEqual((medium.token,),
                              (token_ for token_ in self._database.search()
                               if isinstance(token_, token.Medium)))
        self.assertEqual(medium, self._database.medium(medium.token))
        self.assertCountEqual((album.token,),
                              (token_ for token_ in self._database.search()
                               if isinstance(token_, token.Album)))
        self.assertEqual(album, self._database.album(album.token))

    def test_track_not_found(self):
        with self.assertRaises(KeyError):
            self._database.track(token.Track('foo'))

    def test_medium_not_found(self):
        with self.assertRaises(KeyError):
            self._database.medium(token.Medium('foo'))

    def test_medium_returns_tracks_in_order(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file1',),
            'tracknumber': ('1',),
        }).derive())
        track2 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file2',),
            'tracknumber': ('2',),
        }).derive())
        track_undefined = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file3',)
        }).derive())
        self._database.insert_files((
            scan.AudioFile(filename='/dir1/file1',
                           dirname='/dir1',
                           basename='file1',
                           track=track1),
            scan.AudioFile(filename='/dir1/file2',
                           dirname='/dir1',
                           basename='file2',
                           track=track2),
            scan.AudioFile(filename='/dir1/file3',
                           dirname='/dir1',
                           basename='file3',
                           track=track_undefined),
        ))
        self.assertEqual(
            (track_undefined, track1, track2),
            self._database.medium(track_undefined.medium_token).tracks)

    def test_album_not_found(self):
        with self.assertRaises(KeyError):
            self._database.album(token.Album('foo'))

    def test_album_returns_mediums_in_order(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file1',),
            'discnumber': ('1',),
        }).derive())
        medium1 = entity.Medium(tags=track1.tags, tracks=(track1,))
        track2 = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file2',),
            'discnumber': ('2',),
        }).derive())
        medium2 = entity.Medium(tags=track2.tags, tracks=(track2,))
        track_undefined = entity.Track(tags=tag.Tags({
            tag.FILENAME: ('/dir1/file3',),
        }).derive())
        medium_undefined = entity.Medium(tags=track_undefined.tags,
                                         tracks=(track_undefined,))
        self._database.insert_files((
            scan.AudioFile(filename='/dir1/file1',
                           dirname='/dir1',
                           basename='file1',
                           track=track1),
            scan.AudioFile(filename='/dir1/file2',
                           dirname='/dir1',
                           basename='file2',
                           track=track2),
            scan.AudioFile(filename='/dir1/file3',
                           dirname='/dir1',
                           basename='file3',
                           track=track_undefined),
        ))
        self.assertEqual(
            (medium_undefined, medium1, medium2),
            self._database.album(medium_undefined.album_token).mediums)


if __name__ == '__main__':
    unittest.main()
