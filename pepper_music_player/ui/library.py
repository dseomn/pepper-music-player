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
"""View of the library."""

from importlib import resources

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.player import playlist
from pepper_music_player.ui import library_card


class List(library_card.List[library_card.ListItem]):
    """List of things in the library.

    Attributes:
        search_bar: Widget showing the search bar for this list.
    """

    def __init__(
            self,
            library_db: database.Database,
            playlist_: playlist.Playlist,
    ) -> None:
        """Initializer.

        Args:
            library_db: Library database.
            playlist_: Playlist.
        """
        super().__init__(library_db, library_card.ListItem)
        self._playlist = playlist_
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui', 'library.glade'),
            length=-1,
        )
        # TODO(dseomn): If the library is empty, show a 'Scan' button in the
        # placeholder, and hide the search bar.
        self.widget.set_placeholder(builder.get_object('empty_placeholder'))
        # TODO(dseomn): If the search entry is empty, show a shuffle-like button
        # to change the list to a new random selection from the library.
        # TODO(dseomn): Prevent the Escape key from closing the search bar.
        # TODO(dseomn): Run the default search during __init__(), instead of
        # opening up to an empty list.
        # TODO(dseomn): Maybe put the SearchEntry in the headerbar, instead of a
        # SearchBar?
        self.search_bar: Gtk.SearchBar = builder.get_object('search_bar')
        builder.connect_signals(self)

    def row_activated(
            self,
            row: library_card.ListBoxRow[library_card.ListItem],
    ) -> None:
        """See base class."""
        self._playlist.append(row.library_token)

    def on_search_changed(self, search_entry: Gtk.SearchEntry) -> None:
        """Handler for search_changed."""
        del search_entry  # Unused.
        # TODO(dseomn): Pass search terms to search() below.
        # TODO(dseomn): Search, and add results to self.store, asynchronously.
        self.store.splice(
            0,
            0,
            tuple(map(library_card.ListItem, self.library_db.search())),
        )
