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
"""Tests for pepper_music_player.player.player."""

import datetime
import operator
import os
import tempfile
import time
import unittest
from unittest import mock
import wave

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstApp', '1.0')
from gi.repository import GstApp

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token
from pepper_music_player.player import order
from pepper_music_player.player import player
from pepper_music_player.player import playlist
from pepper_music_player import pubsub

_CHANNEL_COUNT = 1
_SAMPLE_WIDTH_BYTES = 2
_SAMPLE_RATE = 48000

_DEFAULT_DURATION_SECONDS = 0.1


def _audio_data(byte, *, duration_seconds=_DEFAULT_DURATION_SECONDS):
    return byte * (_CHANNEL_COUNT * _SAMPLE_WIDTH_BYTES *
                   round(_SAMPLE_RATE * duration_seconds))


_AUDIO_ZEROES = _audio_data(b'\x00')
_AUDIO_ONES = _audio_data(b'\xff')


class _FakeOrder(order.Order):
    """Fake for Order.

    Attributes:
        playable_units: Sequence of playable units. This Order will start with
            the first one, and return None after the last one.
    """

    def __init__(self):
        self.playable_units = ()

    def _next_or_previous(self, current, *, index_if_none, offset):
        """Implementation of next() and previous().

        Args:
            current: See next() and previous() on base class.
            index_if_none: Which playable unit to return if current is None.
            offset: Offset in self.playable_units to return normally.
        """
        if current is None:
            try:
                return self.playable_units[index_if_none]
            except IndexError:
                return None
        try:
            index = self.playable_units.index(current)
        except ValueError:
            return None
        if 0 <= index + offset < len(self.playable_units):
            return self.playable_units[index + offset]
        else:
            return None

    def next(self, current, *, error_policy=order.ErrorPolicy.DEFAULT):
        """See base class."""
        del error_policy  # Unused.
        return self._next_or_previous(current, index_if_none=0, offset=1)

    def previous(self, current, *, error_policy=order.ErrorPolicy.DEFAULT):
        """See base class."""
        del error_policy  # Unused.
        return self._next_or_previous(current, index_if_none=-1, offset=-1)


class PlayerTest(unittest.TestCase):
    """Tests for player.Player.

    Attributes:
        maxDiff: See base class.
    """
    maxDiff = None

    def setUp(self):
        super().setUp()
        self._pubsub = pubsub.PubSub()
        self._play_status_callback = mock.Mock(spec=())
        self._pubsub.subscribe(player.PlayStatus, self._play_status_callback)
        Gst.init(argv=None)
        self._audio_sink = Gst.parse_launch_full('appsink', None,
                                                 Gst.ParseFlags.FATAL_ERRORS)
        self._player = player.Player(
            pubsub_bus=self._pubsub,
            audio_sink=self._audio_sink,
        )
        self.addCleanup(self._player.stop)
        self._order = _FakeOrder()
        self._player.set_order(self._order)

    def _playable_unit(self, basename, data):
        """Returns a playable unit with the given audio data."""
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        filename = os.path.join(tempdir.name, f'{basename}.wav')
        with wave.open(filename, 'wb') as wave_file:
            wave_file.setnchannels(_CHANNEL_COUNT)
            wave_file.setsampwidth(_SAMPLE_WIDTH_BYTES)
            wave_file.setframerate(_SAMPLE_RATE)
            wave_file.writeframes(data)
        return entity.PlayableUnit(
            track=entity.Track(tags=tag.Tags({tag.FILENAME: (filename,)})),
            playlist_entry=entity.PlaylistEntry(
                library_token=token.Track('ignore-this-token')),
        )

    def _all_audio(self):
        """Returns all audio output after waiting for the output to finish."""
        data = []
        while True:
            sample = GstApp.AppSink.pull_sample(self._audio_sink)
            if sample is None:
                return b''.join(data)
            data.append(sample.get_buffer().map(Gst.MapFlags.READ)[1].data)

    def _deduplicated_status_updates(self):
        """Returns deduplicated PlayStatus messages from pubsub.

        Messages are deduplicated such that:
            1. Any two adjacent, equal messages are collapsed into one.
            2. Any range of message that differ only in a monotonically
               non-decreasing position attribute are collapsed into two
               messages, one for the minimum position and one for the maximum
               position.
        """
        self._pubsub.join()
        statuses = []
        in_a_range_of_messages = False  # Condition 2 from the docstring.
        for mock_call in self._play_status_callback.mock_calls:
            _, (status,), _ = mock_call
            if not statuses:
                statuses.append(status)
            elif status == statuses[-1]:
                pass
            elif all((
                    operator.eq(
                        (
                            status.state,
                            status.playable_unit,
                            status.duration,
                        ),
                        (
                            statuses[-1].state,
                            statuses[-1].playable_unit,
                            statuses[-1].duration,
                        ),
                    ),
                    status.position >= statuses[-1].position,
            )):
                if in_a_range_of_messages:
                    # Continuing the existing range, overwrite the end of the
                    # range.
                    statuses[-1] = status
                else:
                    # Second message in a newly discovered range.
                    in_a_range_of_messages = True
                    statuses.append(status)
            else:
                in_a_range_of_messages = False
                statuses.append(status)
        return statuses

    def test_default_order_is_null(self):
        default_player = player.Player(
            pubsub_bus=self._pubsub,
            audio_sink=self._audio_sink,
        )
        default_player.play()
        self.assertEqual(b'', self._all_audio())

    def test_play_is_gapless(self):
        self._order.playable_units = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            self._playable_unit('ones', _AUDIO_ONES),
        )
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES + _AUDIO_ONES, self._all_audio())

    def test_play_can_repeat_a_track(self):
        track = self._playable_unit('zeroes', _AUDIO_ZEROES).track
        self._order.playable_units = (
            entity.PlayableUnit(
                track=track,
                playlist_entry=entity.PlaylistEntry(
                    library_token=token.Track('ignore-this-token'))),
            entity.PlayableUnit(
                track=track,
                playlist_entry=entity.PlaylistEntry(
                    library_token=token.Track('ignore-this-token'))),
        )
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES * 2, self._all_audio())

    def test_play_resumes_from_pause_and_pause_while_paused_is_noop(self):
        self._order.playable_units = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.play()
        self._player.pause()
        self._player.pause()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_play_while_already_playing_is_noop(self):
        self._order.playable_units = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.play()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_pause_prepares_next_playable_unit(self):
        self._order.playable_units = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.pause()
        self._order.playable_units = ()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_play_specific_unit(self):
        ones = self._playable_unit('ones', _AUDIO_ONES)
        self._order.playable_units = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            ones,
        )
        self._player.play(ones)
        self.assertEqual(_AUDIO_ONES, self._all_audio())

    def test_pause_specific_unit(self):
        ones = self._playable_unit('ones', _AUDIO_ONES)
        self._order.playable_units = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            ones,
        )
        self._player.pause(ones)
        self._player.play()
        self.assertEqual(_AUDIO_ONES, self._all_audio())

    def test_seek(self):
        self._order.playable_units = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.pause()
        self._player.seek(
            datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS) / 2)
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES[len(_AUDIO_ZEROES) // 2:],
                         self._all_audio())

    def test_next_at_end(self):
        self._order.playable_units = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.pause()
        # TODO(https://github.com/PyCQA/pylint/issues/3595): Remove pylint
        # disable.
        self._player.next()  # pylint: disable=not-callable
        self.assertEqual(b'', self._all_audio())

    def test_next_while_playing(self):
        self._order.playable_units = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            self._playable_unit('ones', _AUDIO_ONES),
        )
        self._player.play()
        # TODO(https://github.com/PyCQA/pylint/issues/3595): Remove pylint
        # disable.
        self._player.next()  # pylint: disable=not-callable
        self.assertEqual(_AUDIO_ONES, self._all_audio()[-len(_AUDIO_ONES):])

    def test_next_while_paused(self):
        self._order.playable_units = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            self._playable_unit('ones', _AUDIO_ONES),
        )
        self._player.pause()
        # TODO(https://github.com/PyCQA/pylint/issues/3595): Remove pylint
        # disable.
        self._player.next()  # pylint: disable=not-callable
        self._player.play()
        self.assertEqual(_AUDIO_ONES, self._all_audio())

    def test_previous_restarts_current_if_after_grace_period(self):
        duration = datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS)
        ones = self._playable_unit('ones', _AUDIO_ONES)
        self._order.playable_units = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            ones,
        )
        self._player.pause(ones)
        self._player.seek(duration / 2)
        self._player.previous(grace_period=duration / 4)
        self._player.play()
        self.assertEqual(_AUDIO_ONES, self._all_audio())

    def test_previous_restarts_current_if_no_previous(self):
        self._player.set_order(order.Null())
        self._player.pause(self._playable_unit('zeroes', _AUDIO_ZEROES))
        self._player.previous()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_previous_goes_to_previous(self):
        duration = datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS)
        ones = self._playable_unit('ones', _AUDIO_ONES)
        self._order.playable_units = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            ones,
        )
        self._player.pause(ones)
        self._player.seek(duration / 2)
        self._player.previous(grace_period=duration)
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES + _AUDIO_ONES, self._all_audio())

    def test_previous_noop_if_stopped_with_no_previous(self):
        self._player.previous()
        self._player.play()
        self.assertEqual(b'', self._all_audio())

    def test_previous_while_playing(self):
        self._order.playable_units = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.play()
        self._player.previous()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio()[-len(_AUDIO_ZEROES):])

    def test_logs_and_stops_on_error(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        filename = os.path.join(tempdir.name, 'error.wav')
        with open(filename, 'wb') as fh:
            fh.write(b'This is probably not a valid wav file.')
        self._order.playable_units = (entity.PlayableUnit(
            track=entity.Track(tags=tag.Tags({tag.FILENAME: (filename,)})),
            playlist_entry=entity.PlaylistEntry(
                library_token=token.Track('ignore-this-token')),
        ),)
        with self.assertLogs() as logs:
            self._player.play()
            all_audio = self._all_audio()
        self.assertRegex('\n'.join(logs.output),
                         r'Error from gstreamer element')
        self.assertEqual(b'', all_audio)

    def test_publishes_play_status(self):
        # This uses durations that are longer than the default, since the status
        # updates run in the background and aren't guaranteed to capture every
        # status change.
        zeroes = self._playable_unit('zeroes',
                                     _audio_data(b'\x00', duration_seconds=1.0))
        ones = self._playable_unit('ones',
                                   _audio_data(b'\xff', duration_seconds=1.1))
        time.sleep(1)  # Wait for the initial STOPPED status.
        self._order.playable_units = (zeroes, ones)
        self._pubsub.publish(playlist.Update())
        time.sleep(1)  # Wait for the updated STOPPED status.
        self._player.play()
        self._all_audio()
        time.sleep(1)  # Wait for the final STOPPED status.
        self.assertSequenceEqual(
            (
                player.PlayStatus(
                    state=player.State.STOPPED,
                    capabilities=player.Capabilities.NONE,
                    playable_unit=None,
                    duration=datetime.timedelta(0),
                    position=datetime.timedelta(0),
                ),
                player.PlayStatus(
                    state=player.State.STOPPED,
                    capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                                  player.Capabilities.NEXT |
                                  player.Capabilities.PREVIOUS),
                    playable_unit=None,
                    duration=datetime.timedelta(0),
                    position=datetime.timedelta(0),
                ),
                player.PlayStatus(
                    state=player.State.PLAYING,
                    capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                                  player.Capabilities.NEXT |
                                  player.Capabilities.PREVIOUS),
                    playable_unit=zeroes,
                    duration=datetime.timedelta(seconds=1.0),
                    position=mock.ANY,  # Near the beginning.
                ),
                player.PlayStatus(
                    state=player.State.PLAYING,
                    capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                                  player.Capabilities.NEXT |
                                  player.Capabilities.PREVIOUS),
                    playable_unit=zeroes,
                    duration=datetime.timedelta(seconds=1.0),
                    position=mock.ANY,  # Near the end.
                ),
                player.PlayStatus(
                    state=player.State.PLAYING,
                    capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                                  player.Capabilities.NEXT |
                                  player.Capabilities.PREVIOUS),
                    playable_unit=ones,
                    duration=datetime.timedelta(seconds=1.1),
                    position=mock.ANY,  # Near the beginning.
                ),
                player.PlayStatus(
                    state=player.State.PLAYING,
                    capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                                  player.Capabilities.NEXT |
                                  player.Capabilities.PREVIOUS),
                    playable_unit=ones,
                    duration=datetime.timedelta(seconds=1.1),
                    position=mock.ANY,  # Near the end.
                ),
                player.PlayStatus(
                    state=player.State.STOPPED,
                    capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                                  player.Capabilities.NEXT |
                                  player.Capabilities.PREVIOUS),
                    playable_unit=None,
                    duration=datetime.timedelta(0),
                    position=datetime.timedelta(0),
                ),
            ),
            self._deduplicated_status_updates(),
        )

    def test_publishes_play_status_on_initial_pause(self):
        zeroes = self._playable_unit('zeroes', _AUDIO_ZEROES)
        self._order.playable_units = (zeroes,)
        self._player.pause()
        time.sleep(1)
        self.assertIn(
            player.PlayStatus(
                state=player.State.PAUSED,
                capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                              player.Capabilities.NEXT |
                              player.Capabilities.PREVIOUS),
                playable_unit=zeroes,
                duration=datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS),
                position=datetime.timedelta(0),
            ),
            self._deduplicated_status_updates(),
        )

    def test_publishes_play_status_after_seek_while_paused(self):
        zeroes = self._playable_unit('zeroes', _AUDIO_ZEROES)
        self._order.playable_units = (zeroes,)
        self._player.pause()
        position = datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS) / 2
        self._player.seek(position)
        time.sleep(1)
        self.assertIn(
            player.PlayStatus(
                state=player.State.PAUSED,
                capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                              player.Capabilities.NEXT |
                              player.Capabilities.PREVIOUS),
                playable_unit=zeroes,
                duration=datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS),
                position=position,
            ),
            self._deduplicated_status_updates(),
        )

    def test_publishes_play_status_on_state_change(self,
                                                   async_state_change=False):
        self._audio_sink.set_property('async', async_state_change)
        zeroes = self._playable_unit('zeroes',
                                     _audio_data(b'\x00', duration_seconds=1.0))
        self._order.playable_units = (zeroes,)
        self._player.play()
        time.sleep(0.2)  # Wait for play to start.
        self._player.pause()
        time.sleep(0.2)  # Wait for pause() to generate a PlayStatus.
        self._player.play()
        self._all_audio()
        statuses = self._deduplicated_status_updates()
        sync_pause_status = player.PlayStatus(
            state=player.State.PAUSED,
            capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                          player.Capabilities.NEXT |
                          player.Capabilities.PREVIOUS),
            playable_unit=zeroes,
            duration=datetime.timedelta(seconds=1.0),
            position=mock.ANY,  # Near 0.2.
        )
        sync_play_status = player.PlayStatus(
            state=player.State.PLAYING,
            capabilities=(player.Capabilities.PLAY_OR_PAUSE |
                          player.Capabilities.NEXT |
                          player.Capabilities.PREVIOUS),
            playable_unit=zeroes,
            duration=datetime.timedelta(seconds=1.0),
            position=mock.ANY,  # Near 0.2.
        )
        self.assertIn(sync_pause_status, statuses)
        self.assertIn(sync_play_status,
                      statuses[statuses.index(sync_pause_status):])

    def test_publishes_play_status_on_async_state_change(self):
        self.test_publishes_play_status_on_state_change(async_state_change=True)


if __name__ == '__main__':
    unittest.main()
