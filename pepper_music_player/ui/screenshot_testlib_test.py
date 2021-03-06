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
"""Tests for pepper_music_player.ui.screenshot_testlib."""

import unittest

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.ui import screenshot_testlib


class ScreenshotTest(screenshot_testlib.TestCase):

    def test_register_widget(self):
        widget = Gtk.Label()
        widget.set_text('The quick brown fox jumps over the lazy dog!')
        self.register_widget_screenshot(widget)

    def test_register_narrow_widget(self):
        self.register_narrow_widget_screenshot(
            Gtk.Label.new('Line 1\nLine 2\nLine 3'))


if __name__ == '__main__':
    unittest.main()
