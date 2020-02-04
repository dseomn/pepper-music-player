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
"""Tests for pepper_music_player.ui.alignment."""

import unittest

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.ui import alignment


class TextAlignmentTest(unittest.TestCase):

    def test_set_direction_recursive(self):
        container = Gtk.Button()
        child = Gtk.Label('foo')
        container.add(child)
        alignment.set_direction_recursive(container, Gtk.TextDirection.RTL)
        self.assertIs(Gtk.TextDirection.RTL, container.get_direction())
        self.assertIs(Gtk.TextDirection.RTL, child.get_direction())

    def test_label_unknown(self):
        for initial_direction in (Gtk.TextDirection.LTR, Gtk.TextDirection.RTL):
            with self.subTest(initial_direction):
                label = Gtk.Label.new('123')
                label.set_direction(initial_direction)
                alignment.set_label_direction_from_text(label)
                self.assertEqual(initial_direction, label.get_direction())

    def test_label_ltr(self):
        label = Gtk.Label.new('ABC')
        alignment.set_label_direction_from_text(label)
        self.assertEqual(Gtk.TextDirection.LTR, label.get_direction())

    def test_label_rtl(self):
        label = Gtk.Label.new('אבג')
        alignment.set_label_direction_from_text(label)
        self.assertEqual(Gtk.TextDirection.RTL, label.get_direction())

    def test_aligned_numerical_label(self):
        label = Gtk.Label()
        alignment.fill_aligned_numerical_label(label, '1"23')
        self.assertEqual('<span font_features="tnum">1&quot;23</span>',
                         label.get_label())


if __name__ == '__main__':
    unittest.main()
