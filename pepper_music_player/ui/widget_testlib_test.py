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
"""Tests for pepper_music_player.ui.widget_testlib."""

import unittest

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.ui import widget_testlib

_SAMPLE_TEXT = 'The quick brown fox jumps over the lazy dog!'


class WidgetTestCaseTest(widget_testlib.WidgetTestCase):

    def test_match(self):
        widget = Gtk.Label()
        widget.set_text(_SAMPLE_TEXT)
        self.assert_widget_matches_image('pepper_music_player.ui',
                                         'widget_testlib_test.png', widget)

    def test_mismatch_contents(self):
        widget = Gtk.Label()
        widget.set_markup(f'<u>{_SAMPLE_TEXT}</u>')
        with self.assertRaisesRegex(AssertionError,
                                    'differs from reference image'):
            self.assert_widget_matches_image('pepper_music_player.ui',
                                             'widget_testlib_test.png', widget)


if __name__ == '__main__':
    unittest.main()
