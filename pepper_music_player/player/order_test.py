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
"""Tests for pepper_music_player.player.order."""

import unittest
from unittest import mock

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import token
from pepper_music_player.player import order
from pepper_music_player.player import order_testlib


class StopErrorTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._undecorated = mock.Mock(spec=())
        self._decorated = order.handle_stop_error(self._undecorated)

    def test_handle_stop_error_passes_args(self):
        self._decorated('foo', bar='bar')
        self._undecorated.assert_called_once_with(
            'foo', bar='bar', error_policy=order.ErrorPolicy.RAISE_STOP_ERROR)

    def test_handle_stop_error_passes_raise_policy(self):
        self._decorated(error_policy=order.ErrorPolicy.RETURN_NONE)
        self._undecorated.assert_called_once_with(
            error_policy=order.ErrorPolicy.RAISE_STOP_ERROR)

    def test_handle_stop_error_returns_value(self):
        self._undecorated.return_value = 'foo'
        self.assertEqual('foo', self._decorated())

    def test_handle_stop_error_handles_return_none(self):
        self._undecorated.side_effect = order.StopError('foo')
        with self.assertLogs() as logs:
            self.assertIsNone(
                self._decorated(error_policy=order.ErrorPolicy.RETURN_NONE))
        self.assertRegex('\n'.join(logs.output),
                         r'Stopping due to error(.|\n)*foo')

    def test_handle_stop_error_handles_raise_stop_error(self):
        self._undecorated.side_effect = order.StopError('foo')
        with self.assertRaisesRegex(order.StopError, 'foo'):
            self._decorated(error_policy=order.ErrorPolicy.RAISE_STOP_ERROR)


class LinearEntryTest(order_testlib.TestCase):
    """Test for order.LinearEntry.

    Attributes:
        order: Instance of order.LinearEntry being tested.
    """
    ERROR_POLICY = order.ErrorPolicy.RETURN_NONE

    def setUp(self):
        super().setUp()
        self.order = order.LinearEntry(self.playlist)

    def test_no_current_entry_next(self):
        self.assertIsNone(self.order.next(None))

    def test_no_current_entry_previous(self):
        self.assertIsNone(self.order.previous(None))

    def test_current_entry_not_found_next(self):
        album = self.make_album()
        self.assert_stops_with_error(
            self.order.next,
            entity.PlayableUnit(
                playlist_entry=entity.PlaylistEntry(library_token=album.token),
                track=album.mediums[0].tracks[0]),
            r'playlist entry not found',
        )

    def test_current_entry_not_found_previous(self):
        album = self.make_album()
        self.assert_stops_with_error(
            self.order.previous,
            entity.PlayableUnit(
                playlist_entry=entity.PlaylistEntry(library_token=album.token),
                track=album.mediums[0].tracks[0]),
            r'playlist entry not found',
        )

    def test_current_entry_does_not_contain_track_next(self):
        entry = self.playlist.append(self.make_album().token)
        track = self.make_album().mediums[0].tracks[0]
        self.assert_stops_with_error(
            self.order.next,
            entity.PlayableUnit(playlist_entry=entry, track=track),
            r'track .* does not exist in .* library entity',
        )

    def test_current_entry_does_not_contain_track_previous(self):
        entry = self.playlist.append(self.make_album().token)
        track = self.make_album().mediums[0].tracks[0]
        self.assert_stops_with_error(
            self.order.previous,
            entity.PlayableUnit(playlist_entry=entry, track=track),
            r'track .* does not exist in .* library entity',
        )

    def test_next(self):
        album = self.make_album(track_count=2)
        tracks = album.mediums[0].tracks
        entry = self.playlist.append(album.token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry, track=tracks[1]),
            self.order.next(
                entity.PlayableUnit(playlist_entry=entry, track=tracks[0])))

    def test_previous(self):
        album = self.make_album(track_count=2)
        tracks = album.mediums[0].tracks
        entry = self.playlist.append(album.token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry, track=tracks[0]),
            self.order.previous(
                entity.PlayableUnit(playlist_entry=entry, track=tracks[1])))

    def test_next_stops_at_end_of_entry(self):
        track = self.make_album().mediums[0].tracks[0]
        entry = self.playlist.append(track.token)
        self.assertIsNone(
            self.order.next(
                entity.PlayableUnit(playlist_entry=entry, track=track)))

    def test_previous_stops_at_beginning_of_entry(self):
        track = self.make_album().mediums[0].tracks[0]
        entry = self.playlist.append(track.token)
        self.assertIsNone(
            self.order.previous(
                entity.PlayableUnit(playlist_entry=entry, track=track)))


class LinearEntryRaiseErrorTest(LinearEntryTest):
    ERROR_POLICY = order.ErrorPolicy.RAISE_STOP_ERROR


class LinearTest(LinearEntryTest):
    ERROR_POLICY = order.ErrorPolicy.RETURN_NONE

    def setUp(self):
        super().setUp()
        self.order = order.Linear(self.playlist)

    def test_next_stops_at_end_of_entry(self):
        self.skipTest(
            'This behavior of the parent class does not apply to the child')

    def test_previous_stops_at_beginning_of_entry(self):
        self.skipTest(
            'This behavior of the parent class does not apply to the child')

    def test_next_stops_at_end_of_playlist(self):
        track = self.make_album().mediums[0].tracks[0]
        entry = self.playlist.append(track.token)
        self.assertIsNone(
            self.order.next(
                entity.PlayableUnit(playlist_entry=entry, track=track)))

    def test_previous_stops_at_beginning_of_playlist(self):
        track = self.make_album().mediums[0].tracks[0]
        entry = self.playlist.append(track.token)
        self.assertIsNone(
            self.order.previous(
                entity.PlayableUnit(playlist_entry=entry, track=track)))

    def test_adjacent_entity_does_not_exist_next(self):
        track = self.make_album().mediums[0].tracks[0]
        entry = self.playlist.append(track.token)
        self.playlist.append(token.Track('invalid-token'))
        self.assert_stops_with_error(
            self.order.next,
            entity.PlayableUnit(playlist_entry=entry, track=track),
            r'invalid-token.* does not exist',
        )

    def test_adjacent_entity_does_not_exist_previous(self):
        self.playlist.append(token.Track('invalid-token'))
        track = self.make_album().mediums[0].tracks[0]
        entry = self.playlist.append(track.token)
        self.assert_stops_with_error(
            self.order.previous,
            entity.PlayableUnit(playlist_entry=entry, track=track),
            r'invalid-token.* does not exist',
        )

    def test_next_starts_playlist_at_beginning(self):
        album = self.make_album(track_count=2)
        entry = self.playlist.append(album.token)
        self.playlist.append(self.make_album().token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry,
                                track=album.mediums[0].tracks[0]),
            self.order.next(None))

    def test_previous_starts_playlist_at_end(self):
        self.playlist.append(self.make_album().token)
        album = self.make_album(track_count=2)
        entry = self.playlist.append(album.token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry,
                                track=album.mediums[-1].tracks[-1]),
            self.order.previous(None))

    def test_next_across_entries(self):
        album1 = self.make_album(track_count=2)
        entry1 = self.playlist.append(album1.token)
        album2 = self.make_album(track_count=2)
        entry2 = self.playlist.append(album2.token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry2,
                                track=album2.mediums[0].tracks[0]),
            self.order.next(
                entity.PlayableUnit(playlist_entry=entry1,
                                    track=album1.mediums[-1].tracks[-1])))

    def test_previous_across_entries(self):
        album1 = self.make_album(track_count=2)
        entry1 = self.playlist.append(album1.token)
        album2 = self.make_album(track_count=2)
        entry2 = self.playlist.append(album2.token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry1,
                                track=album1.mediums[-1].tracks[-1]),
            self.order.previous(
                entity.PlayableUnit(playlist_entry=entry2,
                                    track=album2.mediums[0].tracks[0])))


class LinearRaisesErrorTest(LinearTest):
    ERROR_POLICY = order.ErrorPolicy.RAISE_STOP_ERROR


class RepeatTest(LinearTest):
    ERROR_POLICY = order.ErrorPolicy.RETURN_NONE

    def setUp(self):
        super().setUp()
        self.order = order.Repeat(self.playlist)

    def test_next_stops_at_end_of_playlist(self):
        self.skipTest(
            'This behavior of the parent class does not apply to the child.')

    def test_previous_stops_at_beginning_of_playlist(self):
        self.skipTest(
            'This behavior of the parent class does not apply to the child.')

    def test_next_wraps_at_end_of_playlist(self):
        album1 = self.make_album(track_count=2)
        entry1 = self.playlist.append(album1.token)
        album2 = self.make_album(track_count=2)
        entry2 = self.playlist.append(album2.token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry1,
                                track=album1.mediums[0].tracks[0]),
            self.order.next(
                entity.PlayableUnit(playlist_entry=entry2,
                                    track=album2.mediums[-1].tracks[-1])))

    def test_previous_wraps_at_beginning_of_playlist(self):
        album1 = self.make_album(track_count=2)
        entry1 = self.playlist.append(album1.token)
        album2 = self.make_album(track_count=2)
        entry2 = self.playlist.append(album2.token)
        self.assertEqual(
            entity.PlayableUnit(playlist_entry=entry2,
                                track=album2.mediums[-1].tracks[-1]),
            self.order.previous(
                entity.PlayableUnit(playlist_entry=entry1,
                                    track=album1.mediums[0].tracks[0])))


class RepeatRaisesErrorTest(RepeatTest):
    ERROR_POLICY = order.ErrorPolicy.RAISE_STOP_ERROR


if __name__ == '__main__':
    unittest.main()
