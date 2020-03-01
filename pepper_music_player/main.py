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
"""Main application."""

import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.library import scan
from pepper_music_player.player import player
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import application


def main() -> None:
    # TODO(dseomn): Switch to the real default database_dir, once there is one.
    database_dir = '.'
    library_db = database.Database(database_dir=database_dir)
    # TODO(dseomn): Make scanning controllable by the UI instead of doing it
    # here.
    library_scan_dir = os.getenv('PEPPER_SCAN')
    if library_scan_dir:
        library_db.insert_files(scan.scan(library_scan_dir))
    pubsub_bus = pubsub.PubSub()
    player_ = player.Player(pubsub_bus=pubsub_bus)
    playlist_ = playlist.Playlist(
        library_db=library_db,
        pubsub_bus=pubsub_bus,
        database_dir=database_dir,
    )
    application.install_css()
    application.Application(
        library_db,
        pubsub_bus,
        player_,
        playlist_,
    ).window.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()
