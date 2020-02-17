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
"""Tests for pepper_music_player.ui.library."""

import tempfile
import unittest
from unittest import mock

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.library import scan
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import library
from pepper_music_player.ui import library_card
from pepper_music_player.ui import library_card_testlib
from pepper_music_player.ui import screenshot_testlib


class LibraryTest(screenshot_testlib.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._library_db = database.Database(database_dir=tempdir.name)
        self._playlist = playlist.Playlist(
            library_db=self._library_db,
            pubsub_bus=mock.create_autospec(pubsub.PubSub, instance=True),
            database_dir=tempdir.name,
        )
        self._library = library.List(self._library_db, self._playlist)

    def test_empty_list(self):
        self.register_widget_screenshot(self._library.widget)

    def test_activate(self):
        track = entity.Track(tags=tag.Tags({
            '~filename': ('/a/b',),
            '~dirname': ('/a',),
            '~basename': ('b',),
        }).derive())
        self._library_db.insert_files((scan.AudioFile(
            filename='/a/b',
            dirname='/a',
            basename='b',
            track=track,
        ),))
        self._library.store.append(library_card.ListItem(track.token))
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()
        library_card_testlib.activate_row(self._library.widget, track.token)
        self.assertSequenceEqual(
            (track.token,),
            tuple(entry.library_token for entry in self._playlist))


if __name__ == '__main__':
    unittest.main()
