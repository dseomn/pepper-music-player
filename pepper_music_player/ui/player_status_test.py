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
import unittest
from unittest import mock

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.player import player
from pepper_music_player import pubsub
from pepper_music_player.ui import player_status
from pepper_music_player.ui import screenshot_testlib


class ButtonsTest(screenshot_testlib.TestCase):

    def setUp(self):
        super().setUp()
        self._pubsub = pubsub.PubSub()
        self._player = mock.create_autospec(player.Player, instance=True)
        self._buttons = player_status.Buttons(
            pubsub_bus=self._pubsub,
            player_=self._player,
        )

    def _publish_status(self, play_state, capabilities):
        """Publishes an player.PlayStatus.

        Args:
            play_state: State for the published status.
            capabilities: Capabilities for the published status.
        """
        if play_state is player.State.STOPPED:
            duration = datetime.timedelta(0)
            playable_unit = None
        else:
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
            duration = datetime.timedelta(
                seconds=float(track.tags.one(tag.DURATION_SECONDS)))
            playable_unit = entity.PlayableUnit(
                track=track,
                playlist_entry=entity.PlaylistEntry(library_token=track.token))
        self._pubsub.publish(
            player.PlayStatus(
                state=play_state,
                capabilities=capabilities,
                playable_unit=playable_unit,
                duration=duration,
                position=duration / 3,
            ))
        self._pubsub.join()
        GLib.idle_add(Gtk.main_quit, priority=GLib.PRIORITY_LOW)
        Gtk.main()

    def test_stopped_with_empty_playlist(self):
        self._publish_status(player.State.STOPPED, player.Capabilities.NONE)
        self.assertFalse(self._buttons.previous_button.get_sensitive())
        self.assertFalse(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'play', self._buttons.play_pause_stack.get_visible_child_name())
        self.assertFalse(self._buttons.next_button.get_sensitive())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_stopped_with_nonempty_playlist(self):
        self._publish_status(
            player.State.STOPPED,
            (player.Capabilities.PLAY_OR_PAUSE | player.Capabilities.NEXT |
             player.Capabilities.PREVIOUS))
        self.assertTrue(self._buttons.previous_button.get_sensitive())
        self.assertTrue(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'play', self._buttons.play_pause_stack.get_visible_child_name())
        self.assertTrue(self._buttons.next_button.get_sensitive())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_playing(self):
        self._publish_status(
            player.State.PLAYING,
            (player.Capabilities.PLAY_OR_PAUSE | player.Capabilities.NEXT |
             player.Capabilities.PREVIOUS))
        self.assertTrue(self._buttons.previous_button.get_sensitive())
        self.assertTrue(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'pause', self._buttons.play_pause_stack.get_visible_child_name())
        self.assertTrue(self._buttons.next_button.get_sensitive())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_paused(self):
        self._publish_status(
            player.State.PAUSED,
            (player.Capabilities.PLAY_OR_PAUSE | player.Capabilities.NEXT |
             player.Capabilities.PREVIOUS))
        self.assertTrue(self._buttons.previous_button.get_sensitive())
        self.assertTrue(self._buttons.play_pause_button.get_sensitive())
        self.assertEqual(
            'play', self._buttons.play_pause_stack.get_visible_child_name())
        self.assertTrue(self._buttons.next_button.get_sensitive())
        self.register_narrow_widget_screenshot(self._buttons.widget)

    def test_previous_button_goes_previous(self):
        self._buttons.previous_button.clicked()
        self._player.previous.assert_called_once_with()

    def test_play_button_plays(self):
        self._publish_status(player.State.PAUSED,
                             player.Capabilities.PLAY_OR_PAUSE)
        self._buttons.play_pause_button.clicked()
        self._player.play.assert_called_once_with()

    def test_pause_button_pauses(self):
        self._publish_status(player.State.PLAYING,
                             player.Capabilities.PLAY_OR_PAUSE)
        self._buttons.play_pause_button.clicked()
        self._player.pause.assert_called_once_with()

    def test_next_button_goes_next(self):
        self._buttons.next_button.clicked()
        self._player.next.assert_called_once_with()


class PositionSliderTest(screenshot_testlib.TestCase):

    def setUp(self):
        super().setUp()
        self._pubsub = pubsub.PubSub()
        self._player = mock.create_autospec(player.Player, instance=True)
        self._slider = player_status.PositionSlider(
            pubsub_bus=self._pubsub,
            player_=self._player,
        )

    def _publish_status(self, state, *, duration, position):
        """Publishes a PlayStatus and waits for it to propagate."""
        self._pubsub.publish(
            player.PlayStatus(
                state=state,
                # Using NONE and None in the below two fields is wrong for
                # PAUSED and PLAYING, but PositionSlider doesn't use these
                # fields.
                capabilities=player.Capabilities.NONE,
                playable_unit=None,
                duration=duration,
                position=position,
            ))
        self._pubsub.join()
        GLib.idle_add(Gtk.main_quit, priority=GLib.PRIORITY_LOW)
        Gtk.main()

    def _scroll(self, scroll_type, position):
        # TODO(dseomn): Figure out a better way to scroll the slider in tests
        # than emitting signals directly.
        self._slider.slider.emit('change-value', scroll_type,
                                 position.total_seconds())
        GLib.idle_add(Gtk.main_quit, priority=GLib.PRIORITY_LOW)
        Gtk.main()

    def test_stopped(self):
        self._publish_status(player.State.STOPPED,
                             duration=datetime.timedelta(0),
                             position=datetime.timedelta(0))
        self.register_widget_screenshot(self._slider.widget)

    def test_long(self):
        self._publish_status(player.State.PAUSED,
                             duration=datetime.timedelta(hours=5,
                                                         minutes=43,
                                                         seconds=20.9),
                             position=datetime.timedelta(hours=1,
                                                         minutes=23,
                                                         seconds=45.1))
        self.register_widget_screenshot(self._slider.widget)

    def test_seeks(self):
        self._publish_status(player.State.PAUSED,
                             duration=datetime.timedelta(seconds=5),
                             position=datetime.timedelta(0))
        self._scroll(Gtk.ScrollType.JUMP, datetime.timedelta(seconds=1.23))
        self._player.seek.assert_called_once_with(
            datetime.timedelta(seconds=1.23))

    def test_seek_clamps_to_start(self):
        self._publish_status(player.State.PAUSED,
                             duration=datetime.timedelta(seconds=5),
                             position=datetime.timedelta(0))
        self._scroll(Gtk.ScrollType.JUMP, datetime.timedelta(seconds=-1))
        self._player.seek.assert_called_once_with(datetime.timedelta(seconds=0))

    def test_seek_clamps_to_end(self):
        self._publish_status(player.State.PAUSED,
                             duration=datetime.timedelta(seconds=5),
                             position=datetime.timedelta(0))
        self._scroll(Gtk.ScrollType.JUMP, datetime.timedelta(seconds=6))
        self._player.seek.assert_called_once_with(datetime.timedelta(seconds=5))


if __name__ == '__main__':
    unittest.main()
