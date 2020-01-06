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
"""Tests for pepper_music_player.ui.library_card."""

import dataclasses
import tempfile
import unittest

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.library import scan
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token
from pepper_music_player.ui import library_card
from pepper_music_player.ui import screenshot_testlib


@dataclasses.dataclass(frozen=True)
class _FakeLibraryToken(token.LibraryToken):
    pass


class LibraryCardTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._library_db = database.Database(database_dir=tempdir.name)
        self._library_db.reset()
        self._factory = library_card.WidgetFactory(self._library_db)

    def test_unknown_token_type(self):
        with self.assertRaisesRegex(ValueError, 'Unknown library token type'):
            self._factory.build(library_card.ListItem(_FakeLibraryToken('foo')))

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _track_card(
            self,
            *,
            discnumber='1',
            tracknumber='1',
            title='Cool Song',
            artist='Pop Star',
            duration_seconds='123.4',
    ):  # yapf: disable
        tags = {}
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for name, value in (
                ('discnumber', discnumber),
                ('tracknumber', tracknumber),
                ('title', title),
                ('artist', artist),
                ('~duration_seconds', duration_seconds),
        ):  # yapf: disable
            if value is not None:
                tags[name] = (value,)
        track = entity.Track(tags=tag.Tags(tags).derive())
        basename = '-'.join((
            discnumber or '',
            tracknumber or '',
            title or '',
            artist or '',
        ))
        self._library_db.insert_files((scan.AudioFile(
            filename=f'/a/{basename}',
            dirname='/a',
            basename=basename,
            track=track,
        ),))
        return self._factory.build(library_card.ListItem(track.token))

    def test_track_ltr(self):
        screenshot_testlib.register_widget(
            __name__, 'test_track_ltr',
            self._track_card(title='Cool Song', artist='Pop Star'))

    def test_track_rtl(self):
        screenshot_testlib.register_widget(
            __name__, 'test_track_rtl',
            self._track_card(title='אבג', artist='أبجدهو'))

    def test_track_long(self):
        screenshot_testlib.register_widget(
            __name__, 'test_track_long',
            self._track_card(
                discnumber='123456',
                tracknumber='5000000',
                title=' '.join((
                    'What sort of person has a favorite UUID‽',
                    'I do!',
                    'My favorite is bdec4e86-bc40-440f-971d-2464bfab37eba.',
                    "What's your favorite UUID?",
                )),
                artist=' '.join((
                    'אלפבית עברי',
                    'أبجدية عربية',
                    'אלפבית עברי',
                    'أبجدية عربية',
                    'אלפבית עברי',
                    'أبجدية عربية',
                )),
                duration_seconds='12345',
            ))

    def test_track_alignment(self):
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        box.pack_start(
            self._track_card(discnumber=None,
                             tracknumber=None,
                             title=None,
                             artist=None,
                             duration_seconds=None),
            False,
            False,
            0,
        )
        box.pack_start(
            self._track_card(discnumber='2',
                             tracknumber='5',
                             duration_seconds='3'),
            False,
            False,
            0,
        )
        box.pack_start(
            self._track_card(discnumber='123',
                             tracknumber='456',
                             duration_seconds='12345'),
            False,
            False,
            0,
        )
        screenshot_testlib.register_widget(__name__, 'test_track_alignment',
                                           box)


if __name__ == '__main__':
    unittest.main()
