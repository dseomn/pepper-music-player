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
"""Helpers for text direction."""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
gi.require_version('Pango', '1.0')
from gi.repository import Pango


def set_label_direction_from_text(label: Gtk.Label) -> None:
    """Sets the widget direction to match its text contents."""
    direction = Pango.find_base_dir(label.get_text(), length=-1)
    if direction is Pango.Direction.LTR:
        label.set_direction(Gtk.TextDirection.LTR)
    elif direction is Pango.Direction.RTL:
        label.set_direction(Gtk.TextDirection.RTL)
