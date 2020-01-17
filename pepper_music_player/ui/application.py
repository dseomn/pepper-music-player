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
"""Main application window."""

import gi
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.ui import load

# Unfortunately, GTK doesn't seem to support dependency injection very well, so
# this global variable ensures the application CSS is installed at most once.
# GTK already requires all calls to it to be in a single thread, so this
# shouldn't make the thread-safety situation any worse at least.
_css_installed = False


def install_css() -> None:
    """Installs the application's CSS, if it isn't already installed."""
    global _css_installed  # pylint: disable=global-statement
    if _css_installed:
        return
    css = Gtk.CssProvider()
    css.load_from_data(
        load.get_resource('pepper_music_player.ui', 'application.css'))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _css_installed = True


def window() -> Gtk.ApplicationWindow:
    """Returns a new main application window."""
    builder = load.builder_from_resource('pepper_music_player.ui',
                                         'application.glade')
    builder.connect_signals({
        'on_destroy': Gtk.main_quit,
    })
    return builder.get_object('application')
