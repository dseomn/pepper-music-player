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
"""Tests for pepper_music_player.ui.application."""

import tempfile
import unittest

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.ui import application


class ApplicationTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._library_db = database.Database(database_dir=tempdir.name)

    def test_install_css_does_not_raise_exceptions(self):
        # The function is called twice since it has a separate code path if the
        # css is already installed.
        application.install_css()
        application.install_css()

    def test_exit_stops_main_loop(self):
        window = application.window(self._library_db)
        window.show_all()
        GLib.idle_add(window.destroy)
        # This just tests that Gtk.main doesn't run forever.
        # TODO(dseomn): Figure out how to end the test early if Gtk.main is
        # still running after a short time.
        Gtk.main()


if __name__ == '__main__':
    unittest.main()
