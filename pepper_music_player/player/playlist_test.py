# Copyright 2020 Google LLC
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
"""Tests for pepper_music_player.player.playlist."""

import tempfile
import unittest
from unittest import mock

from pepper_music_player.library import database
from pepper_music_player.library import scan
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token
from pepper_music_player.player import audio
from pepper_music_player.player import playlist


def _insert_album(library_db):
    """Inserts an album, then returns it."""
    library_db.insert_files((
        scan.AudioFile(
            filename='/a/1',
            dirname='/a',
            basename='1',
            track=entity.Track(tags=tag.Tags({
                '~filename': ('/a/1',),
                '~dirname': ('/a',),
            })),
        ),
        scan.AudioFile(
            filename='/a/2',
            dirname='/a',
            basename='2',
            track=entity.Track(tags=tag.Tags({
                '~filename': ('/a/2',),
                '~dirname': ('/a',),
            })),
        ),
    ))
    return library_db.album(
        next(
            iter(token_ for token_ in library_db.search()
                 if isinstance(token_, token.Album))))


class PlaylistTest(unittest.TestCase):
    REVERSE_UNORDERED_SELECTS = False

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        library_db = database.Database(database_dir=tempdir.name)
        self._album = _insert_album(library_db)
        self._player = mock.create_autospec(audio.Player, instance=True)
        self._playlist = playlist.Playlist(
            player=self._player,
            library_db=library_db,
            database_dir=tempdir.name,
            reverse_unordered_selects=self.REVERSE_UNORDERED_SELECTS,
        )

    def _next_playable_unit_callback(self):
        self._player.set_next_playable_unit_callback.assert_called()
        args, _ = self._player.set_next_playable_unit_callback.call_args
        (callback,) = args
        return callback

    def test_stops_if_no_first_entry(self):
        self.assertIsNone(self._next_playable_unit_callback()(None))

    def test_stops_if_first_entry_not_found(self):
        self._playlist.append(token.Track('invalid-token'))
        self.assertIsNone(self._next_playable_unit_callback()(None))

    def test_plays_first_entry_track(self):
        track = self._album.mediums[0].tracks[0]
        self._playlist.append(track.token)
        self.assertEqual(track, self._next_playable_unit_callback()(None).track)

    def test_plays_first_entry_medium(self):
        medium = self._album.mediums[0]
        self._playlist.append(medium.token)
        self.assertEqual(medium.tracks[0],
                         self._next_playable_unit_callback()(None).track)

    def test_plays_first_entry_album(self):
        self._playlist.append(self._album.token)
        self.assertEqual(self._album.mediums[0].tracks[0],
                         self._next_playable_unit_callback()(None).track)


class PlaylistReverseUnorderedSelectsTest(PlaylistTest):
    REVERSE_UNORDERED_SELECTS = True


if __name__ == '__main__':
    unittest.main()
