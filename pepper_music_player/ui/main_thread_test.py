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
"""Tests for pepper_music_player.ui.main_thread."""

import threading
import unittest
from unittest import mock

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.ui import main_thread


class RunInMainThreadTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._undecorated_mock = mock.Mock(spec=())
        self._decorated_mock = main_thread.run_in_main_thread(
            self._undecorated_mock)

    def _run_main(self):
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()

    def test_calls_function_in_order(self):
        for i in range(1000):
            self._decorated_mock(i)
        self._run_main()
        self.assertSequenceEqual(tuple(mock.call(i) for i in range(1000)),
                                 self._undecorated_mock.mock_calls)

    def test_runs_in_main_thread(self):
        mock_called_from = []
        self._undecorated_mock.side_effect = (
            lambda: mock_called_from.append(threading.get_ident()))
        thread = threading.Thread(target=self._decorated_mock)
        thread.start()
        thread.join()
        self._run_main()
        self.assertSequenceEqual((threading.get_ident(),), mock_called_from)


if __name__ == '__main__':
    unittest.main()
