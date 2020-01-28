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

from importlib import resources

import gi
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.player import audio
from pepper_music_player.player import playlist
from pepper_music_player.ui import library_card

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
        resources.read_binary('pepper_music_player.ui', 'application.css'))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _css_installed = True


def window(
        library_db: database.Database,
        player: audio.Player,
        playlist_: playlist.Playlist,
) -> Gtk.ApplicationWindow:
    """Returns a new main application window.

    Args:
        library_db: Library database.
        player: Player.
        playlist_: Playlist.
    """
    builder = Gtk.Builder.new_from_string(
        resources.read_text('pepper_music_player.ui', 'application.glade'),
        length=-1,
    )
    builder.connect_signals({
        'on_destroy': Gtk.main_quit,
        # TODO(dseomn): Keep track of the current play/pause state and only show
        # the appropriate button. Also make it insensitive when there's nothing
        # to play.
        'on_pause': lambda button: player.pause(),
        'on_play': lambda button: player.play(),
    })
    library = library_card.List(library_db, playlist_)
    builder.get_object('library').add(library.widget)
    # TODO(dseomn): Show a more sensible slice of the library by default, and
    # add UI controls to search the library.
    library.store.splice(
        0, 0, tuple(map(library_card.ListItem, library_db.search(limit=100))))
    return builder.get_object('application')
