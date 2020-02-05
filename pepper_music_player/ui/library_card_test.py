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
from pepper_music_player.metadata import token
from pepper_music_player.player import audio
from pepper_music_player.player import playlist
from pepper_music_player import pubsub
from pepper_music_player.ui import library_card
from pepper_music_player.ui import screenshot_testlib

_LONG_STR_LTR = ' '.join((
    'What sort of person has a favorite UUID‽',
    'I do!',
    'My favorite is bdec4e86-bc40-440f-971d-2464bfab37eba.',
    "What's your favorite UUID?",
))
_LONG_STR_RTL = ' '.join((
    'אלפבית עברי',
    'أبجدية عربية',
    'אלפבית עברי',
    'أبجدية عربية',
    'אלפבית עברי',
    'أبجدية عربية',
))


@dataclasses.dataclass(frozen=True)
class _FakeLibraryToken(token.LibraryToken):
    pass


class LibraryCardTest(screenshot_testlib.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._library_db = database.Database(database_dir=tempdir.name)
        self._playlist = playlist.Playlist(
            player=mock.create_autospec(audio.Player, instance=True),
            library_db=self._library_db,
            pubsub_bus=mock.create_autospec(pubsub.PubSub, instance=True),
            database_dir=tempdir.name,
        )
        self._library_card_list = library_card.List(self._library_db,
                                                    self._playlist)

    def _set_tokens(self, *tokens):
        """Sets the tokens in self._library_card_list."""
        self._library_card_list.store.splice(
            0, 0, tuple(map(library_card.ListItem, tokens)))
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()

    def test_unknown_token_type(self):
        with self.assertRaisesRegex(ValueError, 'Unknown library token type'):
            # TODO(dseomn): Figure out how to test assertions within a Gtk.main
            # loop, instead of using the private _card method.
            self._library_card_list._card(  # pylint: disable=protected-access
                library_card.ListItem(_FakeLibraryToken('foo')))

    def test_empty_list(self):
        self.register_widget_screenshot(self._library_card_list.widget)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _insert_track(
            self,
            *,
            album='Amazing Hits',
            albumartist='Pop Star',
            discnumber='1',
            media=None,
            discsubtitle=None,
            tracknumber='1',
            title='Cool Song',
            artist='Pop Star',
            date=None,
            duration_seconds='123.4',
    ):  # yapf: disable
        """Inserts a track into the database and returns the new track."""
        basename = '-'.join((
            discnumber or '',
            tracknumber or '',
            title or '',
            artist or '',
            album or '',
        ))
        dirname = '/a'
        filename = f'{dirname}/{basename}'
        tags = {
            '~basename': (basename,),
            '~dirname': (dirname,),
            '~filename': (filename,),
        }
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for name, value in (
                ('album', album),
                ('albumartist', albumartist),
                ('discnumber', discnumber),
                ('media', media),
                ('discsubtitle', discsubtitle),
                ('tracknumber', tracknumber),
                ('title', title),
                ('artist', artist),
                ('date', date),
                ('~duration_seconds', duration_seconds),
        ):  # yapf: disable
            if value is not None:
                tags[name] = (value,)
        track = entity.Track(tags=tag.Tags(tags).derive())
        self._library_db.insert_files((scan.AudioFile(
            filename=filename,
            dirname=dirname,
            basename=basename,
            track=track,
        ),))
        return track

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _insert_medium(
            self,
            *,
            track_count=3,
            **kwargs,
    ):  # yapf: disable
        """Inserts a medium into the database and returns the token."""
        for tracknumber in range(1, track_count + 1):
            track = self._insert_track(
                tracknumber=str(tracknumber),
                title=f'Cool Song #{tracknumber}',
                **kwargs,
            )
        return track.medium_token

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _insert_album(
            self,
            *,
            medium_count=2,
            track_count=3,
            artists=None,
            **kwargs,
    ):  # yapf: disable
        """Inserts an album into the database and returns the token.

        Args:
            medium_count: How many mediums to put on the album.
            track_count: How many tracks to put on each medium.
            artists: Iterable of artists to use for each track (on every
                medium), or None to use the default.
            **kwargs: Extra arguments to _insert_track().
        """
        for discnumber in range(1, medium_count + 1):
            for tracknumber in range(1, track_count + 1):
                extra_kwargs = {}
                if artists is not None:
                    extra_kwargs['artist'] = artists[tracknumber - 1]
                track = self._insert_track(
                    tracknumber=str(tracknumber),
                    title=f'Cool Song #{tracknumber}',
                    discnumber=str(discnumber),
                    discsubtitle=f'Sweet Disc #{discnumber}',
                    **extra_kwargs,
                    **kwargs,
                )
        return track.album_token

    def test_track_ltr(self):
        self._set_tokens(
            self._insert_track(title='Cool Song', artist='Pop Star').token)
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_track_rtl(self):
        self._set_tokens(self._insert_track(title='אבג', artist='ﺄﺒﺟﺪﻫﻭ').token)
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_track_long(self):
        self._set_tokens(
            self._insert_track(
                discnumber='123456',
                tracknumber='5000000',
                title=_LONG_STR_LTR,
                artist=_LONG_STR_RTL,
                duration_seconds='12345',
            ).token)
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_medium_header(self):
        # TODO(dseomn): Figure out an easy way to test the contents of the
        # medium header without relying on screenshot tests or using a private
        # function.
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for header, tags in (
                (None, {}),
                (
                    'Medium: Foo',
                    {
                        tag.DISCSUBTITLE: ('Foo',),
                    },
                ),
                (
                    'Medium 2',
                    {
                        tag.PARSED_DISCNUMBER: (2,),
                    },
                ),
                (
                    'Medium 2: Foo',
                    {
                        tag.PARSED_DISCNUMBER: (2,),
                        tag.DISCSUBTITLE: ('Foo',),
                    },
                ),
                (
                    'CD',
                    {
                        tag.MEDIA: ('CD',),
                    },
                ),
                (
                    'CD: Foo',
                    {
                        tag.MEDIA: ('CD',),
                        tag.DISCSUBTITLE: ('Foo',),
                    },
                ),
                (
                    'CD 2',
                    {
                        tag.MEDIA: ('CD',),
                        tag.PARSED_DISCNUMBER: (2,),
                    },
                ),
                (
                    'CD 2: Foo',
                    {
                        tag.MEDIA: ('CD',),
                        tag.PARSED_DISCNUMBER: (2,),
                        tag.DISCSUBTITLE: ('Foo',),
                    },
                ),
        ):  # yapf: disable
            with self.subTest(header=header, tags=tags):
                self.assertEqual(
                    header,
                    library_card._medium_header(tag.Tags(tags)),  # pylint: disable=protected-access
                )

    def test_medium_no_header(self):
        self._set_tokens(self._insert_medium(discnumber=None))
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_medium_with_header(self):
        self._set_tokens(
            self._insert_medium(media='Digital Media',
                                discsubtitle='Best Disc'))
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_medium_long(self):
        self._set_tokens(
            self._insert_medium(
                media='Super Fancy Best Digital Platinum Edition Media',
                discsubtitle=_LONG_STR_RTL))
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_album(self):
        self._set_tokens(
            self._insert_album(
                albumartist='Pop Star',
                track_count=3,
                artists=('Pop Star', 'Pop Star feat. Friend', 'Pop Star'),
                date='2020-01-19',
            ))
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_album_long(self):
        self._set_tokens(
            self._insert_album(
                album=_LONG_STR_RTL,
                albumartist=_LONG_STR_LTR,
                track_count=3,
                date='2020-01-19',
            ))
        self.register_widget_screenshot(self._library_card_list.widget)

    def test_alignment(self):
        self._set_tokens(
            self._insert_track(
                discnumber=None,
                tracknumber=None,
                title=None,
                artist=None,
                duration_seconds=None,
            ).token,
            self._insert_track(
                discnumber='2',
                tracknumber='5',
                duration_seconds='3',
            ).token,
            self._insert_track(
                discnumber='123',
                tracknumber='456',
                duration_seconds='1234',
            ).token,
            self._insert_medium(album='Standalone Medium'),
            self._insert_album(album='Even Better Top Greatest Hits'),
        )
        self.register_widget_screenshot(self._library_card_list.widget)

    def _activate(self, library_token, widget=None):
        if widget is None:
            widget = self._library_card_list.widget
        if (isinstance(widget, library_card.ListBoxRow) and
                widget.library_token == library_token):
            widget.activate()
            GLib.idle_add(Gtk.main_quit)
            Gtk.main()
            return True
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                if self._activate(library_token, child):
                    if isinstance(widget, library_card.ListBoxRow):
                        # In real usage, activating a child seems to bubble up,
                        # but the activate() method does not seem to bubble up.
                        # This simulates the real behavior.
                        widget.activate()
                        GLib.idle_add(Gtk.main_quit)
                        Gtk.main()
                    return True
        return False

    def test_activate_top_level(self):
        library_token = self._insert_album()
        self._set_tokens(library_token)
        self._activate(library_token)
        self.assertSequenceEqual(
            (library_token,),
            tuple(entry.library_token for entry in self._playlist))

    def test_activate_nested(self):
        album_token = self._insert_album()
        self._set_tokens(album_token)
        activate_token = (
            self._library_db.album(album_token).mediums[0].tracks[0].token)
        self._activate(activate_token)
        self.assertSequenceEqual(
            (activate_token,),
            tuple(entry.library_token for entry in self._playlist))

    def test_activate_multiple(self):
        token1 = self._insert_track(tracknumber='1').token
        token2 = self._insert_track(tracknumber='2').token
        self._set_tokens(token1, token2)
        self._activate(token1)
        self._activate(token2)
        self.assertSequenceEqual(
            (token1, token2),
            tuple(entry.library_token for entry in self._playlist))


if __name__ == '__main__':
    unittest.main()
