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
"""Helpers for testing library_card.List subclasses."""

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.metadata import token
from pepper_music_player.ui import library_card


def activate_row(
        parent: Gtk.Widget,
        library_token: token.LibraryToken,
) -> bool:
    """Simulates the activate signal.

    Args:
        parent: External callers should pass library_card.List.widget;
            internally this is used for recursing into the widget.
        library_token: Which inner row to activate.
    """
    if (isinstance(parent, library_card.ListBoxRow) and
            parent.library_token == library_token):
        parent.activate()
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()
    if isinstance(parent, Gtk.Container):
        for child in parent.get_children():
            activate_row(child, library_token)
