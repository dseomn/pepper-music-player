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
"""Utilities for testing Order implementations."""

import tempfile
import unittest
from unittest import mock

from pepper_music_player.library import database
from pepper_music_player.library import scan
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.player import audio
from pepper_music_player.player import order
from pepper_music_player.player import playlist
from pepper_music_player import pubsub


class TestCase(unittest.TestCase):
    """Base class for Order implementation tests.

    Attributes:
        ERROR_POLICY: Error policy used in the test class. Subclasses can have
            their own subclasses with different values of this to run the same
            tests with different error policies.
        playlist: Playlist to use with the Order.
        library_db: Library database used by the playlist.
    """
    ERROR_POLICY = order.ErrorPolicy.DEFAULT

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.library_db = database.Database(database_dir=tempdir.name)
        self.playlist = playlist.Playlist(
            player=mock.create_autospec(audio.Player, instance=True),
            library_db=self.library_db,
            pubsub_bus=mock.create_autospec(pubsub.PubSub, instance=True),
            database_dir=tempdir.name,
        )
        self._make_album_count = 0

    def make_album(self, medium_count=1, track_count=1):
        """Inserts an album into the database and returns it.

        Args:
            medium_count: Number of mediums on the album.
            track_count: Number of tracks on each medium.
        """
        self._make_album_count += 1
        dirname = f'/{self._make_album_count}'
        files = []
        for discnumber in range(1, medium_count + 1):
            for tracknumber in range(1, track_count + 1):
                basename = f'{discnumber}-{tracknumber}'
                filename = f'{dirname}/{basename}'
                track = entity.Track(tags=tag.Tags({
                    '~filename': (filename,),
                    '~dirname': (dirname,),
                    '~basename': (basename,),
                }).derive())
                files.append(
                    scan.AudioFile(filename=filename,
                                   dirname=dirname,
                                   basename=basename,
                                   track=track))
        self.library_db.insert_files(files)
        return self.library_db.album(track.album_token)

    def assert_stops_with_error(self, method, current, error_regex):
        """Asserts that method(current) causes an error matching error_regex."""
        if self.ERROR_POLICY is order.ErrorPolicy.RETURN_NONE:
            with self.assertLogs() as logs:
                self.assertIsNone(
                    method(current, error_policy=self.ERROR_POLICY))
            self.assertRegex('\n'.join(logs.output), error_regex)
        else:
            assert self.ERROR_POLICY is order.ErrorPolicy.RAISE_STOP_ERROR
            with self.assertRaisesRegex(order.StopError, error_regex):
                method(current, error_policy=self.ERROR_POLICY)

    def assert_stops_with_error_symmetric(self, order_, current, error_regex):
        """Asserts that current causes an error in either direction.

        Args:
            order_: Order being tested.
            current: Playable unit (or None) that causes an error in either the
                previous() or next() direction.
            error_regex: Regular expression matching the error.
        """
        self.assert_stops_with_error(order_.next, current, error_regex)
        self.assert_stops_with_error(order_.previous, current, error_regex)

    def assert_symmetrically_adjacent(self, order_, first, second):
        """Asserts that two playable units are adjacent in both directions.

        Args:
            order_: Order being tested.
            first: First playable unit, or None. This should equal
                order_.previous(second).
            second: Second playable unit, or None. This should equal
                order_.next(first).
        """
        self.assertEqual(second, order_.next(first))
        self.assertEqual(first, order_.previous(second))
