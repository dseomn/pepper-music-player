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

import datetime
from importlib import resources

import frozendict
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.metadata import formatting
from pepper_music_player.player import player
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
        next_button: Button for skipping to the next playable unit. This is
            public for use in tests only.
    """
    _STATE_TO_VISIBLE_BUTTON = frozendict.frozendict({
        player.State.STOPPED: 'play',
        player.State.PAUSED: 'play',
        player.State.PLAYING: 'pause',
    })

    def __init__(
            self,
            *,
            pubsub_bus: pubsub.PubSub,
            player_: player.Player,
    ) -> None:
        """Initializer.

        Args:
            pubsub_bus: PubSub message bus.
            player_: Player.
        """
        self._pubsub = pubsub_bus
        self._player = player_
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
        self.next_button: Gtk.Button = builder.get_object('next_button')
        self._pubsub.subscribe(player.PlayStatus,
                               self._handle_play_status,
                               want_last_message=True)
        builder.connect_signals(self)

    @main_thread.run_in_main_thread
    def _handle_play_status(self, status: player.PlayStatus) -> None:
        self.play_pause_button.set_sensitive(
            bool(status.capabilities & player.Capabilities.PLAY_OR_PAUSE))
        self.play_pause_stack.set_visible_child_name(
            self._STATE_TO_VISIBLE_BUTTON[status.state])
        self.next_button.set_sensitive(
            bool(status.capabilities & player.Capabilities.NEXT))

    def on_play_pause(self, button: Gtk.Button) -> None:
        """Handler for the play/pause button."""
        del button  # Unused.
        if self.play_pause_stack.get_visible_child_name() == 'play':
            self._player.play()
        else:
            self._player.pause()

    def on_next(self, button: Gtk.Button) -> None:
        """Handler for the next button."""
        del button  # Unused.
        self._player.next()


class PositionSlider:
    """Position slider, including labels for the current position and duration.

    Attributes:
        widget: Widget containing the slider and labels.
        slider: Slider for seeking. This is public for use in tests only.
    """

    # TODO(dseomn): Don't immediately seek on every slight drag of the slider.

    def __init__(
            self,
            *,
            pubsub_bus: pubsub.PubSub,
            player_: player.Player,
    ) -> None:
        """Initializer.

        Args:
            pubsub_bus: PubSub message bus.
            player_: Player.
        """
        self._pubsub = pubsub_bus
        self._player = player_
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'player_status_position_slider.glade'),
            length=-1,
        )
        self.widget = builder.get_object('container')
        # https://material.io/design/usability/bidirectionality.html#mirroring-elements
        # "Media controls for playback are always LTR."
        alignment.set_direction_recursive(self.widget, Gtk.TextDirection.LTR)
        self._position: Gtk.Label = builder.get_object('position')
        self._duration: Gtk.Label = builder.get_object('duration')
        self.slider: Gtk.Scale = builder.get_object('slider')
        self._pubsub.subscribe(player.PlayStatus,
                               self._handle_play_status,
                               want_last_message=True)
        builder.connect_signals(self)

    @main_thread.run_in_main_thread
    def _handle_play_status(self, status: player.PlayStatus) -> None:
        """Handler for PlayStatus updates."""
        # TODO(https://github.com/google/yapf/issues/805): Remove line break
        # comments.
        alignment.fill_aligned_numerical_label(
            self._position,
            formatting.format_timedelta(  # Force a line break.
                None
                if status.state is player.State.STOPPED else status.position))
        alignment.fill_aligned_numerical_label(
            self._duration,
            formatting.format_timedelta(  # Force a line break.
                None
                if status.state is player.State.STOPPED else status.duration))
        self.slider.set_range(0.0, status.duration.total_seconds())
        self.slider.set_value(status.position.total_seconds())

    def on_slider_change_value(
            self,
            slider: Gtk.Scale,
            scroll: Gtk.ScrollType,
            value: float,
    ) -> bool:
        """Handler for the slider's change-value signal."""
        del slider, scroll  # Unused.
        lower = self.slider.get_adjustment().get_lower()
        upper = self.slider.get_adjustment().get_upper()
        self._player.seek(
            datetime.timedelta(seconds=min(max(value, lower), upper)))
        return False
