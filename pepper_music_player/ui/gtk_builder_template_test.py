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
"""Tests for pepper_music_player.ui.gtk_builder_template."""

import unittest

import jinja2

from pepper_music_player.ui import gtk_builder_template


class TemplateTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._template = gtk_builder_template.Template("""
            <interface>
                <object class="GtkLabel" id="label">
                    <property name="label">{{ label_text }}</property>
                </object>
            </interface>
        """)

    def test_render_requires_all_variables_to_be_defined(self):
        with self.assertRaises(jinja2.UndefinedError):
            self._template.render()

    def test_render_escapes_markup(self):
        label_text = '<foo><!-- bar --><?quux?>&baz;'
        builder = self._template.render(label_text=label_text)
        self.assertEqual(label_text, builder.get_object('label').get_label())


if __name__ == '__main__':
    unittest.main()
