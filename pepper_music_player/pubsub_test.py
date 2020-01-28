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
"""Tests for pepper_music_player.pubsub."""

import dataclasses
import unittest
from unittest import mock

from pepper_music_player import pubsub


@dataclasses.dataclass(frozen=True)
class _Message(pubsub.Message):
    data: str


@dataclasses.dataclass(frozen=True)
class _OtherMessage(pubsub.Message):
    other_data: int


class PubSubTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._pubsub = pubsub.PubSub()
        self._callback = mock.Mock(spec=())

    def test_subscriber_receives_published_message(self):
        self._pubsub.subscribe(_Message, self._callback)
        self._pubsub.publish(_Message('foo'))
        self._pubsub.join()
        self._callback.assert_called_once_with(_Message('foo'))

    def test_subscriber_receives_subclassed_message(self):
        self._pubsub.subscribe(pubsub.Message, self._callback)
        self._pubsub.publish(_Message('foo'))
        self._pubsub.join()
        self._callback.assert_called_once_with(_Message('foo'))

    def test_subscriber_does_not_receive_unwanted_message(self):
        self._pubsub.subscribe(_OtherMessage, self._callback)
        self._pubsub.publish(_Message('foo'))
        self._pubsub.join()
        self._callback.assert_not_called()

    def test_subscriber_recieves_messages_in_order(self):
        self._pubsub.subscribe(_OtherMessage, self._callback)
        for index in range(1000):
            self._pubsub.publish(_OtherMessage(index))
        self._pubsub.join()
        self.assertSequenceEqual(
            tuple(mock.call(_OtherMessage(index)) for index in range(1000)),
            self._callback.mock_calls,
        )

    def test_callback_exception_is_logged(self):
        self._callback.side_effect = ValueError('kumquat')
        self._pubsub.subscribe(pubsub.Message, self._callback)
        with self.assertLogs() as logs:
            self._pubsub.publish(_Message('cauliflower'))
            self._pubsub.join()
        self.assertRegex(
            '\n'.join(logs.output),
            r'failed to process message.*cauliflower(.|\n)*kumquat')


if __name__ == '__main__':
    unittest.main()
