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
"""Audio player."""

import dataclasses
import threading
from typing import Callable, Optional

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag


@dataclasses.dataclass(frozen=True)
class PlayableUnit:
    """The minimal unit that a player can play, i.e., a track.

    Attributes:
        track: The track to play.
    """
    track: entity.Track


# Given the current playable unit (or None if nothing's playing), returns the
# next playable unit (or None if playback should stop).
NextPlayableUnitCallback = Callable[[Optional[PlayableUnit]],
                                    Optional[PlayableUnit]]


def _parse_pipeline(pipeline_description: str) -> Gst.Element:
    """Returns an Element from a pipeline string."""
    return Gst.parse_launch_full(pipeline_description,
                                 context=None,
                                 flags=Gst.ParseFlags.FATAL_ERRORS)


class Player:
    """Audio player.

    This handles actually playing audio, but does not do any playlist
    management.
    """

    # TODO(dseomn): Add support for seeking, either by the playlist to resume
    # playback where it left off when the app was last closed, or manually by
    # the user.

    def __init__(
            self,
            *,
            audio_sink: Optional[Gst.Element] = None,
    ) -> None:
        """Initializer.

        Args:
            audio_sink: Audio sink to use, or None to use the default. This is
                primarily intended for testing.
        """
        # Thread-safe attributes. These attributes are set only during __init__.
        # The values are also safe to mutate from any thread.
        Gst.init(argv=None)
        self._playbin = _parse_pipeline('playbin')
        self._playbin.set_property('audio-filter', _parse_pipeline('rgvolume'))
        self._playbin.set_property('audio-sink', audio_sink)
        self._playbin.set_property('video-sink', _parse_pipeline('fakesink'))

        self._lock = threading.RLock()

        # Mutable attributes with immutable values. To get or set these
        # attributes, self._lock must be held. However, the values may be used
        # without holding the lock.
        self._playable_unit: Optional[PlayableUnit] = None
        self._next_playable_unit_callback: NextPlayableUnitCallback = (
            lambda _: None)

        self._playbin.connect('about-to-finish',
                              self._prepare_next_playable_unit)

    def set_next_playable_unit_callback(
            self,
            callback: NextPlayableUnitCallback,
    ) -> None:
        """Sets the callback that returns the next thing to play.

        Args:
            callback: Callback that returns the next thing to play, or None if
                playback should stop after the current playable unit. Its only
                argument is the current playable unit, or None if nothing is
                currently playing or paused.
        """
        with self._lock:
            self._next_playable_unit_callback = callback

    def _prepare_next_playable_unit(
            self,
            _element: Optional[Gst.Element] = None,
            *,
            initial: bool = False,
    ) -> None:
        """Prepares the player to start playing whatever is next.

        Args:
            _element: GObject signal handlers must take the signaling object as
                a parameter. This parameter is for compatibility with that; do
                not use it for anything.
            initial: Whether this method is being called to prepare the initial
                playable unit from a stop, or the next unit regardless of the
                current state.
        """
        del _element  # See docstring.
        with self._lock:
            if initial and self._playable_unit is not None:
                # Something is already prepared, and we're only supposed to
                # prepare something if nothing is ready.
                return
            self._playable_unit = self._next_playable_unit_callback(
                self._playable_unit)
            if self._playable_unit is not None:
                self._playbin.set_property(
                    'uri',
                    Gst.filename_to_uri(
                        self._playable_unit.track.tags.one(tag.FILENAME)))

    def play(self) -> None:
        """Starts playing, if possible.

        If something is already playing, this is a no-op. If something is
        paused, this resumes playing. If nothing is playing or paused, this
        tries playing whatever is next. If nothing is playing, paused, or next,
        it's a no-op.
        """
        with self._lock:
            self._prepare_next_playable_unit(initial=True)
            self._playbin.set_state(Gst.State.PLAYING)

    def pause(self) -> None:
        """Pauses playing, if possible.

        If something is already playing, this pauses that. If something is
        paused, this is a no-op. If nothing is playing or paused, this tries
        preparing whatever is next in a paused state. If nothing is playing,
        paused, or next, it's a no-op.
        """
        with self._lock:
            self._prepare_next_playable_unit(initial=True)
            self._playbin.set_state(Gst.State.PAUSED)

    def stop(self) -> None:
        """Stops playing."""
        with self._lock:
            self._playable_unit = None
            self._playbin.set_state(Gst.State.NULL)
