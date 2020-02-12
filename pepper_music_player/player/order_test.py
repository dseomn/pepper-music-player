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
"""Tests for pepper_music_player.player.order."""

import unittest
from unittest import mock

from pepper_music_player.player import order


class StopErrorTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._undecorated = mock.Mock(spec=())
        self._decorated = order.handle_stop_error(self._undecorated)

    def test_handle_stop_error_passes_args(self):
        self._decorated('foo', bar='bar')
        self._undecorated.assert_called_once_with(
            'foo', bar='bar', error_policy=order.ErrorPolicy.RAISE_STOP_ERROR)

    def test_handle_stop_error_passes_raise_policy(self):
        self._decorated(error_policy=order.ErrorPolicy.RETURN_NONE)
        self._undecorated.assert_called_once_with(
            error_policy=order.ErrorPolicy.RAISE_STOP_ERROR)

    def test_handle_stop_error_returns_value(self):
        self._undecorated.return_value = 'foo'
        self.assertEqual('foo', self._decorated())

    def test_handle_stop_error_handles_return_none(self):
        self._undecorated.side_effect = order.StopError('foo')
        with self.assertLogs() as logs:
            self.assertIsNone(
                self._decorated(error_policy=order.ErrorPolicy.RETURN_NONE))
        self.assertRegex('\n'.join(logs.output),
                         r'Stopping due to error(.|\n)*foo')

    def test_handle_stop_error_handles_raise_stop_error(self):
        self._undecorated.side_effect = order.StopError('foo')
        with self.assertRaisesRegex(order.StopError, 'foo'):
            self._decorated(error_policy=order.ErrorPolicy.RAISE_STOP_ERROR)


if __name__ == '__main__':
    unittest.main()
