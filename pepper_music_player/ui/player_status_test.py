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
"""Tests for pepper_music_player.ui.player_status."""

import datetime
import tempfile
import unittest
from unittest import mock

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.library import scan
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.player import audio
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import player_status
from pepper_music_player.ui import screenshot_testlib


class ButtonsTest(screenshot_testlib.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._library_db = database.Database(database_dir=tempdir.name)
        self._pubsub = pubsub.PubSub()
        self._player = mock.create_autospec(audio.Player, instance=True)
        self._playlist = playlist.Playlist(
            player=self._player,
            library_db=self._library_db,
            pubsub_bus=self._pubsub,
            database_dir=tempdir.name,
        )
        self._buttons = player_status.Buttons(
            pubsub_bus=self._pubsub,
            player=self._player,
            playlist_=self._playlist,
        )

    def _insert_track(self):
        track = entity.Track(tags=tag.Tags({
            '~basename': ('b',),
            '~dirname': ('/a',),
            '~filename': ('/a/b',),
            'discnumber': ('1',),
            'tracknumber': ('1',),
            'title': ('Cool Song',),
            'artist': ('Pop Star',),
            '~duration_seconds': ('123',),
        }).derive())
        self._library_db.insert_files((scan.AudioFile(
            filename='/a/b',
            dirname='/a',
            basename='b',
            track=track,
        ),))
        return track

    def _publish_status(self, play_state, *, add_track=True):
        """Publishes an audio.PlayStatus.

        Args:
            play_state: State for the published status.
            add_track: Whether to add a track to the DB and playlist before
                publishing the status. If true, the new track will be in the
                published status.
        """
        if add_track:
            track = self._insert_track()
            duration = datetime.timedelta(
                seconds=float(track.tags.one(tag.DURATION_SECONDS)))
            playable_unit = audio.PlayableUnit(
                track=track, playlist_entry=self._playlist.append(track.token))
        else:
            duration = datetime.timedelta(0)
            playable_unit = None
        self._pubsub.publish(
            audio.PlayStatus(
                state=play_state,
                playable_unit=playable_unit,
                duration=duration,
                position=duration / 3,
            ))
        self._pubsub.join()
        GLib.idle_add(Gtk.main_quit, priority=GLib.PRIORITY_LOW)
        Gtk.main()

    def test_stopped_with_empty_playlist(self):
        self._publish_status(audio.State.STOPPED, add_track=False)
        self.assertFalse(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'play', self._buttons.play_pause_stack.get_visible_child_name())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_stopped_with_nonempty_playlist(self):
        self._publish_status(audio.State.STOPPED, add_track=True)
        self.assertTrue(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'play', self._buttons.play_pause_stack.get_visible_child_name())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_playing(self):
        self._publish_status(audio.State.PLAYING)
        self.assertTrue(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'pause', self._buttons.play_pause_stack.get_visible_child_name())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_paused(self):
        self._publish_status(audio.State.PAUSED)
        self.assertTrue(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'play', self._buttons.play_pause_stack.get_visible_child_name())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_play_button_plays(self):
        self._publish_status(audio.State.PAUSED)
        self._buttons.play_pause_button.clicked()
        self._player.play.assert_called_once_with()

    def test_pause_button_pauses(self):
        self._publish_status(audio.State.PLAYING)
        self._buttons.play_pause_button.clicked()
        self._player.pause.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
