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
"""Tests for pepper_music_player.player.audio."""

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
from pepper_music_player.player import audio
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


def _args_then_none(*args):
    """Yields its arguments, then None forever.

    It seems that the about-to-finish signal sometimes gets sent a few extra
    times when we do anything other than the simplest play() all the way
    through. The exact number of times seems to vary, and doesn't seem
    important. This function makes it easy for tests to return None from the
    NextPlayableUnitCallback after the interesting return values.

    Args:
        *args: What to yield initially.
    """
    yield from args
    while True:
        yield None


class PlayerTest(unittest.TestCase):
    """Tests for audio.Player.

    Attributes:
        maxDiff: See base class.
    """
    maxDiff = None

    def setUp(self):
        super().setUp()
        self._pubsub = pubsub.PubSub()
        self._play_status_callback = mock.Mock(spec=())
        self._pubsub.subscribe(audio.PlayStatus, self._play_status_callback)
        Gst.init(argv=None)
        self._audio_sink = Gst.parse_launch_full('appsink', None,
                                                 Gst.ParseFlags.FATAL_ERRORS)
        self._player = audio.Player(
            pubsub_bus=self._pubsub,
            audio_sink=self._audio_sink,
        )
        self.addCleanup(self._player.stop)
        self._next_playable_unit_callback = mock.Mock(spec=())
        self._player.set_next_playable_unit_callback(
            self._next_playable_unit_callback)

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

    def test_default_next_playable_unit_is_none(self):
        default_player = audio.Player(
            pubsub_bus=self._pubsub,
            audio_sink=self._audio_sink,
        )
        default_player.play()
        self.assertEqual(b'', self._all_audio())

    def test_next_playable_unit_callback_is_called_with_previous_unit(self):
        zeroes = self._playable_unit('zeroes', _AUDIO_ZEROES)
        ones = self._playable_unit('ones', _AUDIO_ONES)
        self._next_playable_unit_callback.side_effect = (zeroes, ones, None)
        self._player.play()
        self._all_audio()  # Wait for the player to finish.
        self.assertSequenceEqual(
            (
                mock.call(None),
                mock.call(zeroes),
                mock.call(ones),
            ),
            self._next_playable_unit_callback.mock_calls,
        )

    def test_play_is_gapless(self):
        self._next_playable_unit_callback.side_effect = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            self._playable_unit('ones', _AUDIO_ONES),
            None,
        )
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES + _AUDIO_ONES, self._all_audio())

    def test_play_can_repeat_a_unit(self):
        playable_unit = self._playable_unit('zeroes', _AUDIO_ZEROES)
        self._next_playable_unit_callback.side_effect = (
            playable_unit,
            playable_unit,
            None,
        )
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES * 2, self._all_audio())

    def test_play_resumes_from_pause_and_pause_while_paused_is_noop(self):
        self._next_playable_unit_callback.side_effect = _args_then_none(
            self._playable_unit('zeroes', _AUDIO_ZEROES))
        self._player.play()
        self._player.pause()
        self._player.pause()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_play_while_already_playing_is_noop(self):
        self._next_playable_unit_callback.side_effect = _args_then_none(
            self._playable_unit('zeroes', _AUDIO_ZEROES))
        self._player.play()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_pause_prepares_next_playable_unit(self):
        self._next_playable_unit_callback.side_effect = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.pause()
        self._next_playable_unit_callback.side_effect = None
        self._next_playable_unit_callback.return_value = None
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_seek(self):
        self._next_playable_unit_callback.side_effect = _args_then_none(
            self._playable_unit('zeroes', _AUDIO_ZEROES))
        self._player.pause()
        self._player.seek(
            datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS) / 2)
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES[len(_AUDIO_ZEROES) // 2:],
                         self._all_audio())

    def test_logs_and_stops_on_error(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        filename = os.path.join(tempdir.name, f'error.wav')
        with open(filename, 'wb') as fh:
            fh.write(b'This is probably not a valid wav file.')
        self._next_playable_unit_callback.side_effect = (entity.PlayableUnit(
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
        self._next_playable_unit_callback.side_effect = (zeroes, ones, None)
        time.sleep(1)  # Wait for the initial STOPPED status.
        self._player.play()
        self._all_audio()
        time.sleep(1)  # Wait for the final STOPPED status.
        self.assertSequenceEqual(
            (
                audio.PlayStatus(
                    state=audio.State.STOPPED,
                    playable_unit=None,
                    duration=datetime.timedelta(0),
                    position=datetime.timedelta(0),
                ),
                audio.PlayStatus(
                    state=audio.State.PLAYING,
                    playable_unit=zeroes,
                    duration=datetime.timedelta(seconds=1.0),
                    position=mock.ANY,  # Near the beginning.
                ),
                audio.PlayStatus(
                    state=audio.State.PLAYING,
                    playable_unit=zeroes,
                    duration=datetime.timedelta(seconds=1.0),
                    position=mock.ANY,  # Near the end.
                ),
                audio.PlayStatus(
                    state=audio.State.PLAYING,
                    playable_unit=ones,
                    duration=datetime.timedelta(seconds=1.1),
                    position=mock.ANY,  # Near the beginning.
                ),
                audio.PlayStatus(
                    state=audio.State.PLAYING,
                    playable_unit=ones,
                    duration=datetime.timedelta(seconds=1.1),
                    position=mock.ANY,  # Near the end.
                ),
                audio.PlayStatus(
                    state=audio.State.STOPPED,
                    playable_unit=None,
                    duration=datetime.timedelta(0),
                    position=datetime.timedelta(0),
                ),
            ),
            self._deduplicated_status_updates(),
        )

    def test_publishes_play_status_on_initial_pause(self):
        zeroes = self._playable_unit('zeroes', _AUDIO_ZEROES)
        self._next_playable_unit_callback.side_effect = _args_then_none(zeroes)
        self._player.pause()
        time.sleep(1)
        self.assertIn(
            audio.PlayStatus(
                state=audio.State.PAUSED,
                playable_unit=zeroes,
                duration=datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS),
                position=datetime.timedelta(0),
            ),
            self._deduplicated_status_updates(),
        )

    def test_publishes_play_status_after_seek_while_paused(self):
        zeroes = self._playable_unit('zeroes', _AUDIO_ZEROES)
        self._next_playable_unit_callback.side_effect = _args_then_none(zeroes)
        self._player.pause()
        position = datetime.timedelta(seconds=_DEFAULT_DURATION_SECONDS) / 2
        self._player.seek(position)
        time.sleep(1)
        self.assertIn(
            audio.PlayStatus(
                state=audio.State.PAUSED,
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
        self._next_playable_unit_callback.side_effect = _args_then_none(zeroes)
        self._player.play()
        time.sleep(0.2)  # Wait for play to start.
        self._player.pause()
        time.sleep(0.2)  # Wait for pause() to generate a PlayStatus.
        self._player.play()
        self._all_audio()
        statuses = self._deduplicated_status_updates()
        sync_pause_status = audio.PlayStatus(
            state=audio.State.PAUSED,
            playable_unit=zeroes,
            duration=datetime.timedelta(seconds=1.0),
            position=mock.ANY,  # Near 0.2.
        )
        sync_play_status = audio.PlayStatus(
            state=audio.State.PLAYING,
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
