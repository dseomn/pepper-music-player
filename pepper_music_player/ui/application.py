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
from pepper_music_player.metadata import token
from pepper_music_player.player import audio
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import library_card
from pepper_music_player.ui import player_status

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


class Application:
    """Main application.

    Attributes:
        window: Main window.
    """

    def __init__(
            self,
            library_db: database.Database,
            pubsub_bus: pubsub.PubSub,
            player: audio.Player,
            playlist_: playlist.Playlist,
    ) -> None:
        """Initializer.

        Args:
            library_db: Library database.
            pubsub_bus: PubSub message bus.
            player: Player.
            playlist_: Playlist.
        """
        self._library_db = library_db
        self._pubsub = pubsub_bus
        self._player = player
        self._playlist = playlist_
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui', 'application.glade'),
            length=-1,
        )
        builder.get_object('player_buttons_placeholder').add(
            player_status.Buttons(
                pubsub_bus=self._pubsub,
                player=self._player,
                playlist_=self._playlist,
            ).widget)
        library = library_card.List(library_db, playlist_)
        builder.get_object('library').add(library.widget)
        # TODO(dseomn): Show a more sensible slice of the library by default,
        # and add UI controls to search the library.
        library.store.splice(
            0, 0,
            tuple(
                library_card.ListItem(library_token)
                for library_token in library_db.search(limit=100)
                if isinstance(library_token, token.Track)))
        self.window: Gtk.ApplicationWindow = builder.get_object('application')
        builder.connect_signals(self)

    def on_destroy(self, window: Gtk.ApplicationWindow) -> None:
        """Handler for the window being destroyed."""
        del window  # Unused.
        Gtk.main_quit()
