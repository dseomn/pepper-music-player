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
"""Cards for things in the library, and lists of those cards."""

from typing import Optional

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('GObject', '2.0')
from gi.repository import GObject
gi.require_version('Gio', '2.0')
from gi.repository import Gio
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.library import database
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token
from pepper_music_player.ui import load


class ListItem(GObject.Object):
    """Data for use in a Gio.ListStore that represents library cards.

    Attributes:
        library_token: Which thing in the library to show a card for.
    """

    def __init__(self, library_token: token.LibraryToken):
        super().__init__()
        self.library_token = library_token


def _fill_aligned_numerical_label(
        label: Gtk.Label,
        size_group: Gtk.SizeGroup,
        text: str,
) -> None:
    """Fills in a numerical label that's aligned with others of its type.

    Args:
        label: Label to fill in.
        size_group: Group to add the label to.
        text: Text to put in the label.
    """
    size_group.add_widget(label)
    label.set_markup(
        f'<span font_features="tnum">{GLib.markup_escape_text(text)}</span>')


def _medium_header(tags: tag.Tags) -> Optional[str]:
    """Returns the medium header, e.g., 'CD 1: Disc Title'."""
    media = tags.singular(tag.MEDIA, default='', separator=' / ')
    number = tags.one_or_none(tag.PARSED_DISCNUMBER)
    title = tags.singular(tag.DISCSUBTITLE, default='')
    if any((media, number, title)):
        return ''.join((
            media or 'Medium',
            f' {number}' if number else '',
            f': {title}' if title else '',
        ))
    else:
        return None


class List:
    """List of library cards.

    Attributes:
        widget: Widget showing the list.
        store: Content in the list.
    """

    def __init__(self, library_db: database.Database) -> None:
        """Initializer.

        Args:
            library_db: Library database.
        """
        self._library_db = library_db
        self._discnumber_size_group = Gtk.SizeGroup.new(
            Gtk.SizeGroupMode.HORIZONTAL)
        self._tracknumber_size_group = Gtk.SizeGroup.new(
            Gtk.SizeGroupMode.HORIZONTAL)
        self._duration_size_group = Gtk.SizeGroup.new(
            Gtk.SizeGroupMode.HORIZONTAL)
        self._date_size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
        self.widget: Gtk.ListBox = load.builder_from_resource(
            'pepper_music_player.ui',
            'library_card_list.glade',
        ).get_object('library_card_list')
        self.store = Gio.ListStore.new(ListItem.__gtype__)
        self.widget.bind_model(self.store, self._card)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _track(
            self,
            track: entity.Track,
            *,
            albumartist: str = '',
            show_discnumber: bool = True,
    ) -> Gtk.Widget:  # yapf: disable
        """Returns a track widget."""
        builder = load.builder_from_resource('pepper_music_player.ui',
                                             'library_card_track.glade')
        discnumber_widget = builder.get_object('discnumber')
        if show_discnumber:
            _fill_aligned_numerical_label(
                discnumber_widget,
                self._discnumber_size_group,
                track.tags.one_or_none(tag.PARSED_DISCNUMBER) or '',
            )
        else:
            discnumber_widget.set_no_show_all(True)
            discnumber_widget.hide()
        _fill_aligned_numerical_label(
            builder.get_object('tracknumber'),
            self._tracknumber_size_group,
            track.tags.one_or_none(tag.PARSED_TRACKNUMBER) or '',
        )
        # TODO(https://discourse.gnome.org/t/is-there-any-way-to-align-a-gtklabel-at-the-horizontal-start-based-on-text-direction/2429):
        # Align RTL text correctly.
        builder.get_object('title').set_text(track.tags.singular(tag.TITLE))
        artist = track.tags.singular(tag.ARTIST)
        artist_widget = builder.get_object('artist')
        if artist != albumartist:
            artist_widget.set_text(artist)
        else:
            artist_widget.set_no_show_all(True)
            artist_widget.hide()
        _fill_aligned_numerical_label(
            builder.get_object('duration'),
            self._duration_size_group,
            track.tags.one_or_none(tag.DURATION_HUMAN) or '',
        )
        return builder.get_object('track')

    def _medium(
            self,
            medium: entity.Medium,
            *,
            albumartist: str = '',
    ) -> Gtk.Widget:
        """Returns a medium widget."""
        builder = load.builder_from_resource('pepper_music_player.ui',
                                             'library_card_medium.glade')
        # TODO(dseomn): Add album information if this is not part of an album
        # card.
        self._discnumber_size_group.add_widget(
            builder.get_object('discnumber_placeholder'))
        header = _medium_header(medium.tags)
        header_widget = builder.get_object('header')
        if header:
            header_widget.set_text(header)
        else:
            header_widget.set_no_show_all(True)
            header_widget.hide()
        tracks = builder.get_object('tracks')
        for track in medium.tracks:
            tracks.insert(self._track(track,
                                      albumartist=albumartist,
                                      show_discnumber=False),
                          position=-1)
        return builder.get_object('medium')

    def _album(self, album: entity.Album) -> Gtk.Widget:
        """Returns an album widget."""
        builder = load.builder_from_resource('pepper_music_player.ui',
                                             'library_card_album.glade')
        builder.get_object('title').set_text(album.tags.singular(tag.ALBUM))
        artist = album.tags.singular(tag.ALBUMARTIST, tag.ARTIST)
        builder.get_object('artist').set_text(artist)
        _fill_aligned_numerical_label(
            builder.get_object('date'),
            self._date_size_group,
            album.tags.singular(tag.DATE, default=''),
        )
        mediums = builder.get_object('mediums')
        for medium in album.mediums:
            mediums.insert(self._medium(medium, albumartist=artist),
                           position=-1)
        return builder.get_object('album')

    def _card(self, item: ListItem) -> Gtk.Widget:
        """Returns a card widget for the given list item."""
        if isinstance(item.library_token, token.Track):
            return self._track(self._library_db.track(item.library_token))
        elif isinstance(item.library_token, token.Medium):
            return self._medium(self._library_db.medium(item.library_token))
        elif isinstance(item.library_token, token.Album):
            return self._album(self._library_db.album(item.library_token))
        else:
            raise ValueError(
                f'Unknown library token type: {item.library_token}')
