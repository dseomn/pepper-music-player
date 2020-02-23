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
from pepper_music_player.player import order
from pepper_music_player.player import player
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import library
from pepper_music_player.ui import library_card
from pepper_music_player.ui import player_status
from pepper_music_player.ui import playlist_view

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
            player_: player.Player,
            playlist_: playlist.Playlist,
    ) -> None:
        """Initializer.

        Args:
            library_db: Library database.
            pubsub_bus: PubSub message bus.
            player_: Player.
            playlist_: Playlist.
        """
        self._library_db = library_db
        self._pubsub = pubsub_bus
        self._player = player_
        self._playlist = playlist_
        # TODO(dseomn): Make the order configurable.
        self._player.set_order(order.Linear(self._playlist))
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui', 'application.glade'),
            length=-1,
        )
        builder.get_object('player_buttons_placeholder').add(
            player_status.Buttons(
                pubsub_bus=self._pubsub,
                player_=self._player,
            ).widget)
        builder.get_object('position_slider_placeholder').add(
            player_status.PositionSlider(
                pubsub_bus=self._pubsub,
                player_=self._player,
            ).widget)
        # TODO(https://gitlab.gnome.org/GNOME/gtk/issues/2463): Change the
        # vscrollbar_policy on the library and playlist to 'automatic'.
        # TODO(dseomn): Make the position of the main Gtk.Paned persist across
        # application restarts, probably using gsettings.
        library_list = library.List(library_db, playlist_)
        builder.get_object('library').add(library_list.widget)
        # TODO(dseomn): Show a more sensible slice of the library by default,
        # and add UI controls to search the library.
        library_list.store.splice(
            0, 0,
            tuple(
                library_card.ListItem(library_token)
                for library_token in library_db.search(limit=100)
                if isinstance(library_token, token.Track)))
        builder.get_object('playlist').add(
            playlist_view.List(
                library_db=library_db,
                playlist_=self._playlist,
                player_=self._player,
                pubsub_bus=self._pubsub,
            ).widget)
        self.window: Gtk.ApplicationWindow = builder.get_object('application')
        builder.connect_signals(self)

    def on_destroy(self, window: Gtk.ApplicationWindow) -> None:
        """Handler for the window being destroyed."""
        del window  # Unused.
        Gtk.main_quit()
