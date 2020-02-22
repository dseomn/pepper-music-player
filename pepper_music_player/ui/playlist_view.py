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
"""View of the playlist."""

from importlib import resources

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import token
from pepper_music_player.player import player
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import library_card
from pepper_music_player.ui import main_thread


class ListItem(library_card.ListItem):
    """List item.

    Attributes:
        playlist_entry: Entry for the row.
    """

    def __init__(self, playlist_entry: entity.PlaylistEntry) -> None:
        super().__init__(playlist_entry.library_token)
        self.playlist_entry = playlist_entry


class List(library_card.List[ListItem]):
    """List of things in the playlist."""

    def __init__(
            self,
            *,
            library_db: database.Database,
            playlist_: playlist.Playlist,
            player_: player.Player,
            pubsub_bus: pubsub.PubSub,
    ) -> None:
        """Initializer.

        Args:
            library_db: Library database.
            playlist_: Playlist.
            player_: Player.
            pubsub_bus: PubSub bus.
        """
        super().__init__(library_db, ListItem)
        self._playlist = playlist_
        self._player = player_
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'playlist_view.glade'),
            length=-1,
        )
        self.list_box.set_placeholder(builder.get_object('empty_placeholder'))
        pubsub_bus.subscribe(playlist.Update,
                             self._update_contents,
                             want_last_message=True)

    @main_thread.run_in_main_thread
    def _update_contents(self, update_message: playlist.Update) -> None:
        """Updates the view based on what's in the playlist."""
        del update_message  # Unused.
        # TODO(dseomn): Only update items that have changed.
        self.store.splice(0, self.store.get_n_items(),
                          tuple(map(ListItem, self._playlist)))

    def row_activated(
            self,
            row: library_card.ListBoxRow[ListItem],
    ) -> None:
        """Plays the given row."""
        if isinstance(row.library_token, token.Track):
            track = self._library_db.track(row.library_token)
        elif isinstance(row.library_token, token.Medium):
            track = self._library_db.medium(row.library_token).tracks[0]
        elif isinstance(row.library_token, token.Album):
            track = (self._library_db.album(
                row.library_token).mediums[0].tracks[0])
        else:
            raise TypeError(f'Unknown library token type: {row.library_token}')
        self._player.play(
            entity.PlayableUnit(playlist_entry=row.list_item.playlist_entry,
                                track=track))
