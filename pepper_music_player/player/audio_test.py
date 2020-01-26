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
import os
import tempfile
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

_CHANNEL_COUNT = 1
_SAMPLE_WIDTH_BYTES = 2
_SAMPLE_RATE = 48000

_AUDIO_DURATION_SECONDS = 0.1
_AUDIO_BYTE_COUNT = (_CHANNEL_COUNT * _SAMPLE_WIDTH_BYTES *
                     round(_SAMPLE_RATE * _AUDIO_DURATION_SECONDS))

_AUDIO_ZEROES = b'\x00' * _AUDIO_BYTE_COUNT
_AUDIO_ONES = b'\xff' * _AUDIO_BYTE_COUNT


class PlayerTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        Gst.init(argv=None)
        self._audio_sink = Gst.parse_launch_full('appsink', None,
                                                 Gst.ParseFlags.FATAL_ERRORS)
        self._player = audio.Player(audio_sink=self._audio_sink)
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
        return audio.PlayableUnit(
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

    def test_default_next_playable_unit_is_none(self):
        default_player = audio.Player(audio_sink=self._audio_sink)
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
        self._next_playable_unit_callback.side_effect = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            None,
        )
        self._player.play()
        self._player.pause()
        self._player.pause()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_play_while_already_playing_is_noop(self):
        self._next_playable_unit_callback.side_effect = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            None,
        )
        self._player.play()
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_pause_prepares_next_playable_unit(self):
        self._next_playable_unit_callback.side_effect = (self._playable_unit(
            'zeroes', _AUDIO_ZEROES),)
        self._player.pause()
        self._next_playable_unit_callback.side_effect = (None,)
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES, self._all_audio())

    def test_seek(self):
        self._next_playable_unit_callback.side_effect = (
            self._playable_unit('zeroes', _AUDIO_ZEROES),
            # It seems that the about-to-finish signal gets sent a few times
            # because the audio is so short and the seek is therefore also close
            # to the end of the audio. That's not really important (in general,
            # or for this test case specifically), but it does mean we need to
            # return None a few extra times.
            None,
            None,
            None,
        )
        self._player.pause()
        self._player.seek(
            datetime.timedelta(seconds=_AUDIO_DURATION_SECONDS) / 2)
        self._player.play()
        self.assertEqual(_AUDIO_ZEROES[len(_AUDIO_ZEROES) // 2:],
                         self._all_audio())


if __name__ == '__main__':
    unittest.main()
