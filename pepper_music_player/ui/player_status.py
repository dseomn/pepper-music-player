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
"""Widgets for controlling and displaying the player status."""

from importlib import resources

import frozendict
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.player import audio
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import alignment
from pepper_music_player.ui import main_thread


class Buttons:
    """Main control buttons for the player.

    Attributes:
        widget: Widget for the buttons.
        play_pause_button: Button for playing or pausing. This is public for use
            in tests only.
        play_pause_stack: Stack with two children, 'play' and 'pause', to
            indicate which button is shown. This is public for use in tests
            only.
    """
    _STATE_TO_VISIBLE_BUTTON = frozendict.frozendict({
        audio.State.STOPPED: 'play',
        audio.State.PAUSED: 'play',
        audio.State.PLAYING: 'pause',
    })

    def __init__(
            self,
            *,
            pubsub_bus: pubsub.PubSub,
            player: audio.Player,
            playlist_: playlist.Playlist,
    ) -> None:
        """Initializer.

        Args:
            pubsub_bus: PubSub message bus.
            player: Player.
            playlist_: Playlist.
        """
        self._pubsub = pubsub_bus
        self._player = player
        self._playlist = playlist_
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'player_status_buttons.glade'),
            length=-1,
        )
        self.widget = builder.get_object('buttons')
        # https://material.io/design/usability/bidirectionality.html#mirroring-elements
        # "Media controls for playback are always LTR."
        alignment.set_direction_recursive(self.widget, Gtk.TextDirection.LTR)
        self.play_pause_button: Gtk.Button = builder.get_object(
            'play_pause_button')
        self.play_pause_stack: Gtk.Stack = builder.get_object(
            'play_pause_stack')
        self._pubsub.subscribe(audio.PlayStatus,
                               self._handle_play_status,
                               want_last_message=True)
        self._pubsub.subscribe(playlist.Update,
                               self._handle_playlist_update,
                               want_last_message=True)
        builder.connect_signals(self)

    @main_thread.run_in_main_thread
    def _handle_play_status(self, status: audio.PlayStatus) -> None:
        self.play_pause_stack.set_visible_child_name(
            self._STATE_TO_VISIBLE_BUTTON[status.state])

    @main_thread.run_in_main_thread
    def _handle_playlist_update(self, update: playlist.Update) -> None:
        del update  # Unused.
        self.play_pause_button.set_sensitive(bool(self._playlist))

    def on_play_pause(self, button: Gtk.Button) -> None:
        """Handler for the play/pause button."""
        del button  # Unused.
        if self.play_pause_stack.get_visible_child_name() == 'play':
            self._player.play()
        else:
            self._player.pause()
