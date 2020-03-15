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
gi.require_version('Pango', '1.0')
from gi.repository import Pango

from pepper_music_player.ui import alignment


def _pango_attr_list_types(attributes):
    """Returns the types of all attributes in the given Pango.AttrList."""
    # Pango.AttrList does not appear to have any normal ways to access its
    # contents, so this is a bit of a hack.
    types = []
    attributes.filter(lambda attribute: types.append(attribute.klass.type))
    return types


class AutoAlignTest(unittest.TestCase):

    def test_direction_manual(self):
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for style_class, direction in (
                ('direction-ltr', Gtk.TextDirection.LTR),
                ('direction-rtl', Gtk.TextDirection.RTL),
        ):  # yapf: disable
            with self.subTest(style_class):
                container = Gtk.Button()
                child = Gtk.Label.new('foo')
                container.add(child)
                container.get_style_context().add_class(style_class)
                alignment.auto_align(container)
                self.assertIs(direction, container.get_direction())
                self.assertIs(direction, child.get_direction())

    def test_direction_auto(self):
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for test_name, initial_direction, text, expected_direction in (
                ('unknown_ltr', Gtk.TextDirection.LTR, '123',
                 Gtk.TextDirection.LTR),
                ('unknown_rtl', Gtk.TextDirection.RTL, '123',
                 Gtk.TextDirection.RTL),
                ('ltr', Gtk.TextDirection.RTL, 'ABC', Gtk.TextDirection.LTR),
                ('rtl', Gtk.TextDirection.LTR, 'אבג', Gtk.TextDirection.RTL),
        ):  # yapf: disable
            with self.subTest(test_name):
                label = Gtk.Label.new(text)
                label.set_direction(initial_direction)
                label.get_style_context().add_class('direction-auto')
                alignment.auto_align(label)
                self.assertEqual(expected_direction, label.get_direction())

    def test_numerical(self):
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for test_name, builder_xml, expected_attribute_types in (
                (
                    'without_original_attributes',
                    """
                        <interface>
                            <object class="GtkLabel" id="label">
                                <style>
                                  <class name="numerical"/>
                                </style>
                            </object>
                        </interface>
                    """,
                    (Pango.AttrType.FONT_FEATURES,),
                ),
                (
                    'with_original_attributes',
                    """
                        <interface>
                            <object class="GtkLabel" id="label">
                                <style>
                                  <class name="numerical"/>
                                </style>
                                <attributes>
                                    <attribute name="weight" value="bold" />
                                </attributes>
                            </object>
                        </interface>
                    """,
                    (Pango.AttrType.FONT_FEATURES, Pango.AttrType.WEIGHT),
                ),
        ):  # yapf: disable
            with self.subTest(test_name):
                label = Gtk.Builder.new_from_string(
                    builder_xml, length=-1).get_object('label')
                alignment.auto_align(label)
                self.assertCountEqual(
                    expected_attribute_types,
                    _pango_attr_list_types(label.get_attributes()))
                self.assertIs(Gtk.TextDirection.LTR, label.get_direction())

    def test_recurses(self):
        container = Gtk.Button()
        container.get_style_context().add_class('direction-rtl')
        child = Gtk.Label.new('foo')
        child.get_style_context().add_class('direction-ltr')
        container.add(child)
        alignment.auto_align(container)
        self.assertIs(Gtk.TextDirection.RTL, container.get_direction())
        self.assertIs(Gtk.TextDirection.LTR, child.get_direction())


if __name__ == '__main__':
    unittest.main()
