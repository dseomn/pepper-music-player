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

import collections
import dataclasses
import datetime
import enum
import functools
import logging
import operator
import threading
import time
from typing import Callable, Deque, Optional

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player import pubsub


@dataclasses.dataclass(frozen=True)
class PlayableUnit:
    """The minimal unit that a player can play, i.e., a track.

    Attributes:
        track: The track to play.
        playlist_entry: Where the track is in a playlist. The Player doesn't use
            this itself, but it can be useful for a playlist's
            NextPlayableUnitCallback.
    """
    track: entity.Track
    playlist_entry: entity.PlaylistEntry


# Given the current playable unit (or None if nothing's playing), returns the
# next playable unit (or None if playback should stop).
NextPlayableUnitCallback = Callable[[Optional[PlayableUnit]],
                                    Optional[PlayableUnit]]


class State(enum.Enum):
    """State of the player.

    Attributes:
        STOPPED: Nothing is playing or ready to play.
        PAUSED: Something is ready, but not playing.
        PLAYING: Something is actively playing.
    """
    STOPPED = enum.auto()
    PAUSED = enum.auto()
    PLAYING = enum.auto()


@dataclasses.dataclass(frozen=True)
class PlayStatus(pubsub.Message):
    """Status update on what is currently playing.

    Attributes:
        state: Current state of playback.
        playable_unit: The current playable unit, or None if state is STOPPED.
        duration: Duration of the current playable unit.
        position: Position of the player within the current playable unit.
    """
    state: State
    playable_unit: Optional[PlayableUnit]
    duration: datetime.timedelta
    position: datetime.timedelta


def _parse_pipeline(pipeline_description: str) -> Gst.Element:
    """Returns an Element from a pipeline string."""
    return Gst.parse_launch_full(pipeline_description,
                                 context=None,
                                 flags=Gst.ParseFlags.FATAL_ERRORS)


def _timedelta_to_gst_clock_time(timedelta: datetime.timedelta) -> int:
    return round(1000 * timedelta / datetime.timedelta(microseconds=1))


def _gst_clock_time_to_timedelta(gst_clock_time: int) -> datetime.timedelta:
    return datetime.timedelta(microseconds=gst_clock_time / 1000)


class Player:
    """Audio player.

    This handles actually playing audio, but does not do any playlist
    management.
    """

    def __init__(
            self,
            *,
            pubsub_bus: pubsub.PubSub,
            audio_sink: Optional[Gst.Element] = None,
    ) -> None:
        """Initializer.

        Args:
            pubsub_bus: Where to send status updates.
            audio_sink: Audio sink to use, or None to use the default. This is
                primarily intended for testing.
        """
        # Thread-safe attributes. These attributes are set only during __init__.
        # The values are also safe to mutate from any thread.
        self._pubsub = pubsub_bus
        Gst.init(argv=None)
        self._playbin = _parse_pipeline('playbin')
        self._playbin.set_property('audio-filter', _parse_pipeline('rgvolume'))
        self._playbin.set_property('audio-sink', audio_sink)
        self._playbin.set_property('video-sink', _parse_pipeline('fakesink'))
        self._state_change_counter = threading.Semaphore(0)

        self._lock = threading.RLock()

        # Mutable attributes, protected by the lock.
        self._state = State.STOPPED  # Target state.
        self._state_has_stabilized = True  # If the target state is current.
        self._playable_units: Deque[PlayableUnit] = collections.deque()
        self._next_playable_unit_callback: NextPlayableUnitCallback = (
            lambda _: None)
        self._next_stream_is_first_after_stop = True
        self._current_duration = datetime.timedelta(0)

        threading.Thread(
            target=self._handle_messages,
            args=(self._playbin.get_bus(),),
            daemon=True,
        ).start()
        self._playbin.connect('about-to-finish',
                              self._prepare_next_playable_unit)

        threading.Thread(target=self._poll_status, daemon=True).start()

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
            if initial and self._playable_units:
                # Something is already prepared, and we're only supposed to
                # prepare something if nothing is ready.
                return
            next_playable_unit = self._next_playable_unit_callback(
                self._playable_units[-1] if self._playable_units else None)
            if next_playable_unit is None:
                return
            self._playable_units.append(next_playable_unit)
            self._playbin.set_property(
                'uri',
                Gst.filename_to_uri(
                    next_playable_unit.track.tags.one(tag.FILENAME)))

    def _poll_status(
            self,
            *,
            inter_update_delay_seconds: float = 0.02,
    ) -> None:
        """Periodically sends status updates to pubsub, in a daemon thread.

        Args:
            inter_update_delay_seconds: How long to sleep between updates when
                not in a steady state.
        """
        while True:
            with self._lock:
                state = self._state
                state_has_stabilized = self._state_has_stabilized
                playable_unit = (self._playable_units[0]
                                 if self._playable_units else None)
                duration = self._current_duration
            position_ok, position_gst_time = self._playbin.query_position(
                Gst.Format.TIME)
            if state_has_stabilized:
                self._pubsub.publish(
                    PlayStatus(
                        state=state,
                        playable_unit=playable_unit,
                        duration=duration,
                        position=(
                            _gst_clock_time_to_timedelta(position_gst_time)
                            if position_ok else datetime.timedelta(0)),
                    ))
            if state is State.PLAYING or not state_has_stabilized:
                time.sleep(inter_update_delay_seconds)
            else:
                self._state_change_counter.acquire()

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
            self._state = State.PLAYING
            self._state_has_stabilized = False
        self._state_change_counter.release()

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
            self._state = State.PAUSED
            self._state_has_stabilized = False
        self._state_change_counter.release()

    def stop(self) -> None:
        """Stops playing."""
        with self._lock:
            self._playable_units.clear()
            self._playbin.set_state(Gst.State.NULL)
            self._state = State.STOPPED
            self._state_has_stabilized = True
            self._next_stream_is_first_after_stop = True
            self._current_duration = datetime.timedelta(0)
        self._state_change_counter.release()

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def seek(
            self,
            position: datetime.timedelta,
            *,
            state_change_timeout: datetime.timedelta = datetime.timedelta(
                milliseconds=100),
    ) -> None:  # yapf: disable
        """Seeks to the given position.

        Args:
            position: Offset from the beginning of the playable unit to seek to.
            state_change_timeout: How long to wait for the player to settle
                before attempting to seek.
        """
        self._playbin.get_state(
            _timedelta_to_gst_clock_time(state_change_timeout))
        self._playbin.seek_simple(Gst.Format.TIME,
                                  Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                                  _timedelta_to_gst_clock_time(position))

    def _on_end_of_stream(self, message: Gst.Message) -> None:
        del message  # Unused.
        self.stop()

    def _on_error(self, message: Gst.Message) -> None:
        gerror, debug = message.parse_error()
        logging.error(
            'Error from gstreamer element %s: %s%s',
            message.src.get_name(),
            gerror.message,
            '' if debug is None else f'\n{debug}',
        )
        self.stop()

    def _on_stream_start(self, message: Gst.Message) -> None:
        del message  # Unused.
        with self._lock:
            self._state_has_stabilized = True
            if not self._next_stream_is_first_after_stop:
                self._playable_units.popleft()
            self._next_stream_is_first_after_stop = False
            duration_ok, duration_gst_time = self._playbin.query_duration(
                Gst.Format.TIME)
            self._current_duration = (
                _gst_clock_time_to_timedelta(duration_gst_time)
                if duration_ok else datetime.timedelta(0))

    def _handle_messages(self, bus: Gst.Bus) -> None:
        """Handles messages from gstreamer in a daemon thread."""
        handlers = {
            Gst.MessageType.EOS: self._on_end_of_stream,
            Gst.MessageType.ERROR: self._on_error,
            Gst.MessageType.STREAM_START: self._on_stream_start,
        }
        message_type_mask = functools.reduce(operator.or_, handlers.keys(),
                                             Gst.MessageType.UNKNOWN)
        while True:
            message = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE,
                                             message_type_mask)
            try:
                handlers[message.type](message)
            except Exception:  # pylint: disable=broad-except
                logging.exception('Error handling gstreamer message of type %s',
                                  message.type)
