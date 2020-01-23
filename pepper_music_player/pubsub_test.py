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
import time
import threading
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
        self.addCleanup(self._pubsub.shutdown)

    def test_subscriber_receives_published_message(self):
        barrier = threading.Barrier(2)
        callback = mock.Mock(spec=(), side_effect=barrier.wait)
        self._pubsub.subscribe(_Message, callback)
        self._pubsub.publish(_Message('foo'))
        barrier.wait()
        callback.assert_called_once_with(_Message('foo'))

    def test_subscriber_receives_subclassed_message(self):
        barrier = threading.Barrier(2)
        callback = mock.Mock(spec=(), side_effect=barrier.wait)
        self._pubsub.subscribe(pubsub.Message, callback)
        self._pubsub.publish(_Message('foo'))
        barrier.wait()
        callback.assert_called_once_with(_Message('foo'))

    def test_subscriber_does_not_receive_unwanted_message(self):
        callback = mock.Mock(spec=())
        self._pubsub.subscribe(_OtherMessage, callback)
        self._pubsub.publish(_Message('foo'))
        # This tests that the callback is not getting called, so a barrier
        # wouldn't work.
        time.sleep(1)
        callback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
