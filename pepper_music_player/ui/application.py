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
import threading

import frozendict
import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.metadata import token
from pepper_music_player.player import audio
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import alignment
from pepper_music_player.ui import library_card

# Unfortunately, GTK doesn't seem to support dependency injection very well, so
# this global variable ensures the application CSS is installed at most once.
# GTK already requires all calls to it to be in a single thread, so this
# shouldn't make the thread-safety situation any worse at least.
_css_installed = False

_STATE_TO_VISIBLE_BUTTON = frozendict.frozendict({
    audio.State.STOPPED: 'play',
    audio.State.PAUSED: 'play',
    audio.State.PLAYING: 'pause',
})


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
        play_pause_button: Button for playing or pausing. This is public for use
            in tests only.
        play_pause_stack: Stack with two children, 'play' and 'pause', to
            indicate which button is shown. This is public for use in tests
            only.
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
        self._lock = threading.Lock()
        self._play_status = None
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui', 'application.glade'),
            length=-1,
        )
        # https://material.io/design/usability/bidirectionality.html#mirroring-elements
        # "Media controls for playback are always LTR."
        alignment.set_direction_recursive(
            builder.get_object('playback_buttons'), Gtk.TextDirection.LTR)
        self.play_pause_button: Gtk.Button = builder.get_object(
            'play_pause_button')
        self.play_pause_stack: Gtk.Stack = builder.get_object(
            'play_pause_stack')
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
        self._pubsub.subscribe(audio.PlayStatus,
                               self._handle_play_status,
                               want_last_message=True)
        self._pubsub.subscribe(playlist.Update, self._handle_playlist_update)
        builder.connect_signals(self)

    def _update_status(self) -> None:
        with self._lock:
            status = self._play_status
        self.play_pause_button.set_sensitive(bool(self._playlist))
        self.play_pause_stack.set_visible_child_name(
            _STATE_TO_VISIBLE_BUTTON[status.state])

    def _handle_play_status(self, status: audio.PlayStatus) -> None:
        with self._lock:
            self._play_status = status
        GLib.idle_add(self._update_status)

    def _handle_playlist_update(self, update: playlist.Update) -> None:
        del update  # Unused.
        GLib.idle_add(self._update_status)

    def on_destroy(self, window: Gtk.ApplicationWindow) -> None:
        """Handler for the window being destroyed."""
        del window  # Unused.
        Gtk.main_quit()

    def on_play_pause(self, button: Gtk.Button) -> None:
        """Handler for the play/pause button."""
        del button  # Unused.
        if self.play_pause_stack.get_visible_child_name() == 'play':
            self._player.play()
        else:
            self._player.pause()
