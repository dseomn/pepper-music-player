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
from typing import Callable, Deque, Optional, Sequence, Tuple, TypeVar, Union

import frozendict
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.player import order
from pepper_music_player.player import playlist
from pepper_music_player import pubsub

T = TypeVar('T')


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


_GST_STATE_TO_STATE = frozendict.frozendict({
    Gst.State.NULL: State.STOPPED,
    Gst.State.PAUSED: State.PAUSED,
    Gst.State.PLAYING: State.PLAYING,
})


class Capabilities(enum.Flag):
    """Capabilities of the player.

    Attributes:
        NONE: No capabilities.
        PLAY_OR_PAUSE: There is a currently playing or paused track, or a call
            to play() or pause() would start a new track. This flag would
            generally be unset when the playlist is empty.
        NEXT: Calling next() would have some effect. I.e., the player is not
            stopped with nothing to play next.
        PREVIOUS: Calling previous() would have some effect. I.e., the player is
            not stopped with no previous playable unit.
    """
    NONE = 0
    PLAY_OR_PAUSE = enum.auto()
    NEXT = enum.auto()
    PREVIOUS = enum.auto()


@dataclasses.dataclass(frozen=True)
class PlayStatus(pubsub.Message):
    """Status update on what is currently playing.

    Attributes:
        state: Current state of playback.
        capabilities: Player's capabilities.
        playable_unit: The current playable unit, or None if state is STOPPED.
        duration: Duration of the current playable unit.
        position: Position of the player within the current playable unit.
    """
    state: State
    capabilities: Capabilities
    playable_unit: Optional[entity.PlayableUnit]
    duration: datetime.timedelta
    position: datetime.timedelta


class _Recalculate(enum.Enum):
    token = enum.auto()


# Placeholder for stale values.
_RECALCULATE = _Recalculate.token


def _parse_pipeline(pipeline_description: str) -> Gst.Element:
    """Returns an Element from a pipeline string."""
    return Gst.parse_launch_full(pipeline_description,
                                 context=None,
                                 flags=Gst.ParseFlags.FATAL_ERRORS)


def _timedelta_to_gst_clock_time(timedelta: datetime.timedelta) -> int:
    return round(1000 * timedelta / datetime.timedelta(microseconds=1))


def _gst_clock_time_to_timedelta(gst_clock_time: int) -> datetime.timedelta:
    return datetime.timedelta(microseconds=gst_clock_time / 1000)


def _gst_query_to_timedelta_or_zero(
        query: Callable[[Gst.Format], Tuple[bool, int]]) -> datetime.timedelta:
    """Runs a gstreamer time query.

    Args:
        query: A bound Gst.Element.query_duration or Gst.Element.query_position
            method.

    Returns:
        The query result on success, or datetime.timedelta(0) on failure.
    """
    ok, gst_time = query(Gst.Format.TIME)
    if ok:
        return _gst_clock_time_to_timedelta(gst_time)
    else:
        return datetime.timedelta(0)


def _first_or_none(sequence: Sequence[T]) -> Optional[T]:
    return sequence[0] if sequence else None


class Player:
    """Audio player."""

    def __init__(
            self,
            *,
            pubsub_bus: pubsub.PubSub,
            audio_sink: Optional[Gst.Element] = None,
    ) -> None:
        """Initializer.

        Args:
            pubsub_bus: PubSub bus.
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
        self._status_change_counter = threading.Semaphore(0)

        self._lock = threading.RLock()

        # Mutable attributes, protected by the lock.
        self._ignore_messages_before_seqnum = Gst.SEQNUM_INVALID
        self._ignore_messages_before_now()
        self._state = State.STOPPED  # Target state.
        self._state_has_stabilized = True  # If the target state is current.
        self._capabilities: Union[Capabilities, _Recalculate] = _RECALCULATE
        self._playable_units: Deque[entity.PlayableUnit] = collections.deque()
        self._order: order.Order = order.Null()
        self._next_stream_is_first = True
        self._current_duration: Union[datetime.timedelta,
                                      _Recalculate] = (datetime.timedelta(0))

        threading.Thread(
            target=self._handle_messages,
            args=(self._playbin.get_bus(),),
            daemon=True,
        ).start()
        self._playbin.connect(
            'about-to-finish',
            # The about-to-finish signal is called from a gstreamer streaming
            # thread, which means it can deadlock with state changes from other
            # threads. The timeout prevents that deadlock, at the expense of
            # some risk that playback will stop unexpectedly when the next unit
            # isn't prepared due to a timeout.
            functools.partial(self._prepare_next_playable_unit,
                              lock_timeout_seconds=0.1))

        self._pubsub.subscribe(playlist.Update, self._handle_playlist_update)

        threading.Thread(target=self._poll_status, daemon=True).start()

    def _ignore_messages_before_now(self) -> None:
        """Causes messages before the present to be ignored.

        When setting the state to NULL, many things are reset, but old messages
        can still be received in Python. Those old messages do not apply to
        anything after the state changes to NULL.
        """
        with self._lock:
            self._ignore_messages_before_seqnum = Gst.util_seqnum_next()
            logging.debug('Ignoring messages before seqnum=%r',
                          self._ignore_messages_before_seqnum)

    def set_order(self, order_: order.Order) -> None:
        """Sets the play order."""
        logging.debug('Player.set_order(%r)', order_)
        with self._lock:
            self._order = order_
            self._capabilities = _RECALCULATE
        self._status_change_counter.release()

    def _prepare_next_playable_unit(
            self,
            element: Optional[Gst.Element] = None,
            *,
            lock_timeout_seconds: float = -1,
            initial: bool = False,
            playable_unit: Optional[entity.PlayableUnit] = None,
    ) -> None:
        """Prepares the player to start playing whatever is next.

        Args:
            element: GObject signal handlers must take the signaling object as a
                parameter. This parameter is for compatibility with that; do not
                use it for anything.
            lock_timeout_seconds: How long to wait for the lock before giving
                up, or a negative number to wait indefinitely.
            initial: Whether this method is being called to prepare the initial
                playable unit from a stop, or the next unit regardless of the
                current state.
            playable_unit: Unit to prepare, or None to use self._order.
        """
        del element  # See docstring.
        if not self._lock.acquire(timeout=lock_timeout_seconds):
            logging.error(
                'Unable to acquire lock to prepare next playable unit after %s '
                'seconds.',
                lock_timeout_seconds,
            )
            return
        try:
            if initial and self._playable_units:
                logging.debug(
                    'Not preparing anything, because something is already '
                    'prepared.')
                return
            next_playable_unit = playable_unit or self._order.next(
                self._playable_units[-1] if self._playable_units else None)
            if next_playable_unit is None:
                logging.debug('Nothing to prepare.')
                return
            logging.debug('Preparing %r', next_playable_unit)
            self._playable_units.append(next_playable_unit)
            self._playbin.set_property(
                'uri',
                Gst.filename_to_uri(
                    next_playable_unit.track.tags.one(tag.FILENAME)))
        finally:
            self._lock.release()

    def _try_set_current_duration(self) -> None:
        """Attempts to set the current duration if it's None."""
        with self._lock:
            if self._current_duration is not _RECALCULATE:
                return
            duration_ok, duration_gst_time = self._playbin.query_duration(
                Gst.Format.TIME)
            if not duration_ok:
                return
            self._current_duration = _gst_clock_time_to_timedelta(
                duration_gst_time)
            logging.debug('Current duration: %r', self._current_duration)

    def _update_capabilities(self) -> None:
        """Updates self._capabilities if needed."""
        with self._lock:
            if self._capabilities is not _RECALCULATE:
                return
            current_unit = _first_or_none(self._playable_units)
            next_unit = self._order.next(current_unit)
            previous_unit = self._order.previous(current_unit)
            self._capabilities = Capabilities.NONE
            if self._state is not State.STOPPED or next_unit is not None:
                self._capabilities |= Capabilities.PLAY_OR_PAUSE
                self._capabilities |= Capabilities.NEXT
            if self._state is not State.STOPPED or previous_unit is not None:
                self._capabilities |= Capabilities.PREVIOUS
            logging.debug('Current capabilities: %r', self._capabilities)

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
                self._update_capabilities()
                state = self._state
                state_has_stabilized = self._state_has_stabilized
                capabilities = self._capabilities
                playable_unit = _first_or_none(self._playable_units)
                self._try_set_current_duration()
                duration = self._current_duration
            position = _gst_query_to_timedelta_or_zero(
                self._playbin.query_position)
            fully_stabilized = all((
                state_has_stabilized,
                duration is not None,
                # There seems to be a race condition between _poll_status() and
                # _on_stream_start(), where _poll_status() can get the position
                # from track N+1 before _on_stream_start() is called to remove
                # track N from self._playable_units. Since gstreamer doesn't
                # seem to provide a way to detect this race condition, we just
                # ignore status updates at the very beginning of a track when
                # the state is PLAYING.
                (state is not State.PLAYING or
                 position > datetime.timedelta(milliseconds=200)),
            ))
            if fully_stabilized:
                logging.debug('Publishing PlayStatus.')
                self._pubsub.publish(
                    PlayStatus(
                        state=state,
                        capabilities=capabilities,
                        playable_unit=playable_unit,
                        duration=duration,
                        position=position,
                    ))
            else:
                logging.debug(
                    'Not publishing PlayStatus, because it is not stabilized.')
            if state is State.PLAYING or not fully_stabilized:
                self._status_change_counter.acquire(
                    timeout=inter_update_delay_seconds)
            else:
                self._status_change_counter.acquire()

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _wait_for_state_change(
            self,
            timeout: datetime.timedelta = datetime.timedelta(milliseconds=100),
    ) -> None:  # yapf: disable
        """Hacky workaround for a bunch of race conditions."""
        result = self._playbin.get_state(_timedelta_to_gst_clock_time(timeout))
        logging.debug('get_state() result: %r', result)

    def _play_or_pause(
            self,
            gst_state: Gst.State,
            state: State,
            playable_unit: Optional[entity.PlayableUnit],
    ) -> None:
        """Implementation for both play() and pause()."""
        with self._lock:
            if playable_unit is not None:
                logging.debug(
                    'Stopping before play/pause of a specific playable unit.')
                self.stop()
                logging.debug(
                    'Done stopping before play/pause of a specific playable '
                    'unit.')
            self._prepare_next_playable_unit(initial=True,
                                             playable_unit=playable_unit)
            self._wait_for_state_change()
            logging.debug('Setting state to %r', gst_state)
            state_change = self._playbin.set_state(gst_state)
            logging.debug('set_state() result: %r', state_change)
            self._state = state
            self._state_has_stabilized = (state_change is
                                          Gst.StateChangeReturn.SUCCESS)
            self._capabilities = _RECALCULATE
        self._status_change_counter.release()

    def play(self, playable_unit: Optional[entity.PlayableUnit] = None) -> None:
        """Starts playing, if possible.

        If something is already playing, this is a no-op. If something is
        paused, this resumes playing. If nothing is playing or paused, this
        tries playing whatever is next. If nothing is playing, paused, or next,
        it's a no-op.

        Args:
            playable_unit: If specified, start playing the given unit from the
                beginning instead of the behavior described above.
        """
        self._play_or_pause(Gst.State.PLAYING, State.PLAYING, playable_unit)

    def pause(
            self,
            playable_unit: Optional[entity.PlayableUnit] = None,
    ) -> None:
        """Pauses playing, if possible.

        If something is already playing, this pauses that. If something is
        paused, this is a no-op. If nothing is playing or paused, this tries
        preparing whatever is next in a paused state. If nothing is playing,
        paused, or next, it's a no-op.

        Args:
            playable_unit: If specified, pause at the beginning of the given
                unit instead of the behavior described above.
        """
        self._play_or_pause(Gst.State.PAUSED, State.PAUSED, playable_unit)

    def stop(self) -> None:
        """Stops playing."""
        with self._lock:
            self._playable_units.clear()
            self._wait_for_state_change()
            self._ignore_messages_before_now()
            logging.debug('Setting state to NULL.')
            state_change = self._playbin.set_state(Gst.State.NULL)
            logging.debug('set_state() result: %r', state_change)
            self._state = State.STOPPED
            self._state_has_stabilized = True
            self._capabilities = _RECALCULATE
            self._next_stream_is_first = True
            self._current_duration = datetime.timedelta(0)
        self._status_change_counter.release()

    def seek(self, position: datetime.timedelta) -> None:
        """Seeks to the given position.

        Args:
            position: Offset from the beginning of the playable unit to seek to.
        """
        self._wait_for_state_change()
        logging.debug('Seeking to %r', position)
        self._playbin.seek_simple(Gst.Format.TIME,
                                  Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                                  _timedelta_to_gst_clock_time(position))
        logging.debug('Done seeking.')
        self._wait_for_state_change()

    def next(self) -> None:
        """Advances to the next playable unit, or stops if there isn't one."""
        with self._lock:
            next_unit = self._order.next(_first_or_none(self._playable_units))
            logging.debug('Going to next playable unit: %r', next_unit)
            if next_unit is None:
                self.stop()
            elif self._state is State.PLAYING:
                self.play(next_unit)
            else:
                self.pause(next_unit)
            logging.debug('Done going to next playable unit.')

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def previous(
            self,
            *,
            grace_period: datetime.timedelta = datetime.timedelta(seconds=2),
    ) -> None:  # yapf: disable
        """Restarts the current playable unit, or goes to the previous one.

        Args:
            grace_period: If the current position is within this distance from
                the beginning of the current playable unit, try going to the
                previous unit; otherwise, restart the current unit.
        """
        with self._lock:
            position = _gst_query_to_timedelta_or_zero(
                self._playbin.query_position)
            current_unit = _first_or_none(self._playable_units)
            if position > grace_period:
                unit_to_start = current_unit
            else:
                unit_to_start = (self._order.previous(current_unit) or
                                 current_unit)
            logging.debug(
                'Going to (potentially) previous playable unit: '
                'current=%r, going_to=%r',
                current_unit,
                unit_to_start,
            )
            if unit_to_start is None:
                self.stop()
            elif self._state is State.PLAYING:
                self.play(unit_to_start)
            else:
                self.pause(unit_to_start)
            logging.debug('Done going to (potentially) previous playable unit.')

    def _on_end_of_stream(self, message: Gst.Message) -> None:
        del message  # Unused.
        logging.debug('End of stream.')
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

    def _on_async_done(self, message: Gst.Message) -> None:
        """Handles ASYNC_DONE."""
        del message  # Unused.
        with self._lock:
            result = self._playbin.get_state(timeout=0)
            logging.debug(
                'Async operation done: desired state = %r, current state = %r',
                self._state, result)
            _, gst_state, _ = result
            if _GST_STATE_TO_STATE.get(gst_state) is self._state:
                self._state_has_stabilized = True
        self._status_change_counter.release()

    def _on_stream_start(self, message: Gst.Message) -> None:
        """Handles STREAM_START."""
        del message  # Unused.
        with self._lock:
            logging.debug('Stream started.')
            self._state_has_stabilized = True
            if not self._next_stream_is_first:
                logging.debug('Removing stale playable unit from old stream.')
                self._playable_units.popleft()
                self._capabilities = _RECALCULATE
            self._next_stream_is_first = False
            self._current_duration = _RECALCULATE
            self._try_set_current_duration()
        self._status_change_counter.release()

    def _handle_messages(self, bus: Gst.Bus) -> None:
        """Handles messages from gstreamer in a daemon thread."""
        handlers = {
            Gst.MessageType.EOS: self._on_end_of_stream,
            Gst.MessageType.ERROR: self._on_error,
            Gst.MessageType.ASYNC_DONE: self._on_async_done,
            Gst.MessageType.STREAM_START: self._on_stream_start,
        }
        message_type_mask = functools.reduce(operator.or_, handlers.keys(),
                                             Gst.MessageType.UNKNOWN)
        while True:
            message = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE,
                                             message_type_mask)
            with self._lock:
                if Gst.util_seqnum_compare(
                        message.seqnum,
                        self._ignore_messages_before_seqnum) < 0:
                    logging.debug(
                        'Ignoring old message of type %r with seqnum %r',
                        message.type, message.seqnum)
                    continue
                try:
                    handlers[message.type](message)
                except Exception:  # pylint: disable=broad-except
                    logging.exception(
                        'Error handling gstreamer message of type %s',
                        message.type)

    def _handle_playlist_update(self, update: playlist.Update) -> None:
        del update  # Unused.
        with self._lock:
            self._capabilities = _RECALCULATE
        self._status_change_counter.release()
