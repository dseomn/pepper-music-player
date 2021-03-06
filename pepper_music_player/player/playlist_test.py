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
from pepper_music_player.player import playlist
from pepper_music_player import pubsub


def _insert_album(library_db, album_name):
    """Inserts an album, then returns it."""
    tracks = (
        entity.Track(tags=tag.Tags({
            '~filename': (f'/{album_name}/1.1',),
            '~dirname': (f'/{album_name}',),
            '~basename': ('1.1',),
            'album': (album_name,),
            'discnumber': ('1',),
        }).derive()),
        entity.Track(tags=tag.Tags({
            '~filename': (f'/{album_name}/1.2',),
            '~dirname': (f'/{album_name}',),
            '~basename': ('1.2',),
            'album': (album_name,),
            'discnumber': ('1',),
        }).derive()),
        entity.Track(tags=tag.Tags({
            '~filename': (f'/{album_name}/2.1',),
            '~dirname': (f'/{album_name}',),
            '~basename': ('2.1',),
            'album': (album_name,),
            'discnumber': ('2',),
        }).derive()),
        entity.Track(tags=tag.Tags({
            '~filename': (f'/{album_name}/2.2',),
            '~dirname': (f'/{album_name}',),
            '~basename': ('2.2',),
            'album': (album_name,),
            'discnumber': ('2',),
        }).derive()),
    )
    for track in tracks:
        library_db.insert_files((scan.AudioFile(
            filename=track.tags.one(tag.FILENAME),
            dirname=track.tags.one(tag.DIRNAME),
            basename=track.tags.one(tag.BASENAME),
            track=track,
        ),))
    return library_db.album(tracks[0].album_token)


class PlaylistTest(unittest.TestCase):
    REVERSE_UNORDERED_SELECTS = False

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        library_db = database.Database(database_dir=tempdir.name)
        self._pubsub = pubsub.PubSub()
        self._update_callback = mock.Mock(spec=())
        self._pubsub.subscribe(playlist.Update, self._update_callback)
        self._album = _insert_album(library_db, 'album')
        self._playlist = playlist.Playlist(
            library_db=library_db,
            pubsub_bus=self._pubsub,
            database_dir=tempdir.name,
            reverse_unordered_selects=self.REVERSE_UNORDERED_SELECTS,
        )

    def test_playable_units_entry_not_found(self):
        with self.assertRaises(KeyError):
            self._playlist.playable_units(
                entity.PlaylistEntry(library_token=self._album.token))

    def test_playable_units_library_entity_not_found(self):
        entry = self._playlist.append(token.Track('invalid-token'))
        with self.assertRaises(KeyError):
            self._playlist.playable_units(entry)

    def test_playable_units_for_track(self):
        entry = self._playlist.append(self._album.mediums[0].tracks[0].token)
        self.assertSequenceEqual(
            (entity.PlayableUnit(playlist_entry=entry,
                                 track=self._album.mediums[0].tracks[0]),),
            self._playlist.playable_units(entry),
        )

    def test_playable_units_for_medium(self):
        entry = self._playlist.append(self._album.mediums[0].token)
        self.assertSequenceEqual(
            (
                entity.PlayableUnit(playlist_entry=entry,
                                    track=self._album.mediums[0].tracks[0]),
                entity.PlayableUnit(playlist_entry=entry,
                                    track=self._album.mediums[0].tracks[1]),
            ),
            self._playlist.playable_units(entry),
        )

    def test_playable_units_for_album(self):
        entry = self._playlist.append(self._album.token)
        self.assertSequenceEqual(
            (
                entity.PlayableUnit(playlist_entry=entry,
                                    track=self._album.mediums[0].tracks[0]),
                entity.PlayableUnit(playlist_entry=entry,
                                    track=self._album.mediums[0].tracks[1]),
                entity.PlayableUnit(playlist_entry=entry,
                                    track=self._album.mediums[1].tracks[0]),
                entity.PlayableUnit(playlist_entry=entry,
                                    track=self._album.mediums[1].tracks[1]),
            ),
            self._playlist.playable_units(entry),
        )

    def test_next_entry_at_beginning(self):
        entry = self._playlist.append(self._album.token)
        self.assertEqual(entry, self._playlist.next_entry(None))

    def test_next_entry(self):
        entry1 = self._playlist.append(self._album.mediums[1].token)
        entry2 = self._playlist.append(self._album.mediums[0].token)
        self.assertEqual(entry2, self._playlist.next_entry(entry1.token))

    def test_next_entry_no_first_entry(self):
        with self.assertRaisesRegex(LookupError, 'no first entry'):
            self._playlist.next_entry(None)

    def test_next_entry_at_end(self):
        entry = self._playlist.append(self._album.token)
        with self.assertRaisesRegex(LookupError, 'at the end'):
            self._playlist.next_entry(entry.token)

    def test_previous_entry_at_end(self):
        entry = self._playlist.append(self._album.token)
        self.assertEqual(entry, self._playlist.previous_entry(None))

    def test_previous_entry(self):
        entry1 = self._playlist.append(self._album.mediums[1].token)
        entry2 = self._playlist.append(self._album.mediums[0].token)
        self.assertEqual(entry1, self._playlist.previous_entry(entry2.token))

    def test_previous_entry_no_last_entry(self):
        with self.assertRaisesRegex(LookupError, 'no last entry'):
            self._playlist.previous_entry(None)

    def test_previous_entry_at_beginning(self):
        entry = self._playlist.append(self._album.token)
        with self.assertRaisesRegex(LookupError, 'at the beginning'):
            self._playlist.previous_entry(entry.token)

    def test_bool_empty(self):
        self.assertFalse(self._playlist)

    def test_bool_non_empty(self):
        self._playlist.append(self._album.token)
        self.assertTrue(self._playlist)

    def test_iter_empty(self):
        self.assertSequenceEqual((), tuple(self._playlist))

    def test_iter(self):
        entry1 = self._playlist.append(self._album.mediums[0].token)
        entry2 = self._playlist.append(self._album.mediums[1].token)
        self.assertSequenceEqual((entry1, entry2), tuple(self._playlist))

    def test_sends_initial_update(self):
        self._pubsub.join()
        self._update_callback.assert_called_once_with(playlist.Update())

    def test_sends_update_on_append(self):
        self._pubsub.join()
        self._update_callback.reset_mock()
        self._playlist.append(self._album.token)
        self._pubsub.join()
        self._update_callback.assert_called_once_with(playlist.Update())


class PlaylistReverseUnorderedSelectsTest(PlaylistTest):
    REVERSE_UNORDERED_SELECTS = True


if __name__ == '__main__':
    unittest.main()
