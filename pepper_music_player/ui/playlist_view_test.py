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
"""Tests for pepper_music_player.ui.playlist_view."""

import datetime
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
from pepper_music_player.player import player
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import library_card_testlib
from pepper_music_player.ui import playlist_view
from pepper_music_player.ui import screenshot_testlib


class PlaylistViewTest(screenshot_testlib.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._library_db = database.Database(database_dir=tempdir.name)
        self._pubsub = pubsub.PubSub()
        self.addCleanup(self._pubsub.join)
        self._playlist = playlist.Playlist(
            library_db=self._library_db,
            pubsub_bus=self._pubsub,
            database_dir=tempdir.name,
        )
        self._player = mock.create_autospec(player.Player, instance=True)
        self._playlist_view = playlist_view.List(
            library_db=self._library_db,
            playlist_=self._playlist,
            player_=self._player,
            pubsub_bus=self._pubsub,
        )
        self._pubsub.join()
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()

    def _insert_album(self, *, directory='/a'):
        """Returns a new album and its playlist entry."""
        for discnumber in ('1', '2'):
            for tracknumber in ('1', '2'):
                basename = f'{discnumber}-{tracknumber}'
                filename = f'{directory}/{basename}'
                track = entity.Track(tags=tag.Tags({
                    '~filename': (filename,),
                    '~dirname': (directory,),
                    '~basename': (basename,),
                    'discnumber': (discnumber,),
                    'tracknumber': (tracknumber,),
                }).derive())
                self._library_db.insert_files((scan.AudioFile(
                    filename=filename,
                    dirname=directory,
                    basename=basename,
                    track=track,
                ),))
        entry = self._playlist.append(track.album_token)
        self._pubsub.join()
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()
        return self._library_db.album(track.album_token), entry

    def test_empty_list(self):
        self._pubsub.publish(
            player.PlayStatus(
                state=player.State.STOPPED,
                capabilities=player.Capabilities.NONE,
                playable_unit=None,
                duration=datetime.timedelta(0),
                position=datetime.timedelta(0),
            ))
        self._pubsub.join()
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()
        self.register_widget_screenshot(self._playlist_view.widget)

    def test_current_track(self):
        album, entry = self._insert_album(directory='/a')
        self._insert_album(directory='/b')
        self._pubsub.publish(
            player.PlayStatus(
                state=player.State.PAUSED,
                capabilities=player.Capabilities.NONE,
                playable_unit=entity.PlayableUnit(
                    playlist_entry=entry,
                    track=album.mediums[0].tracks[0],
                ),
                duration=datetime.timedelta(0),
                position=datetime.timedelta(0),
            ))
        self._pubsub.join()
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()
        self.register_widget_screenshot(self._playlist_view.widget)

    def test_activate_track(self):
        album, entry = self._insert_album()
        library_card_testlib.activate_row(self._playlist_view.widget,
                                          album.mediums[0].tracks[1].token)
        self._player.play.assert_called_once_with(
            entity.PlayableUnit(playlist_entry=entry,
                                track=album.mediums[0].tracks[1]))

    def test_activate_medium(self):
        album, entry = self._insert_album()
        library_card_testlib.activate_row(self._playlist_view.widget,
                                          album.mediums[1].token)
        self._player.play.assert_called_once_with(
            entity.PlayableUnit(playlist_entry=entry,
                                track=album.mediums[1].tracks[0]))

    def test_activate_album(self):
        album, entry = self._insert_album()
        library_card_testlib.activate_row(self._playlist_view.widget,
                                          album.token)
        self._player.play.assert_called_once_with(
            entity.PlayableUnit(playlist_entry=entry,
                                track=album.mediums[0].tracks[0]))


if __name__ == '__main__':
    unittest.main()
