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

import enum
from importlib import resources
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
from pepper_music_player.player import playlist
from pepper_music_player.ui import text_direction


class ListItem(GObject.Object):
    """Data for use in a Gio.ListStore that represents library cards.

    Attributes:
        library_token: Which thing in the library to show a card for.
    """

    def __init__(self, library_token: token.LibraryToken):
        super().__init__()
        self.library_token = library_token


class ListBoxRow(Gtk.ListBoxRow):
    """Row that represents a library entity in a ListBox.

    Attributes:
        library_token: Which thing in the library this row shows.
    """

    def __init__(
            self,
            library_token: token.LibraryToken,
            child: Gtk.Widget,
    ) -> None:
        super().__init__()
        self.library_token = library_token
        self.add(child)


class _SignalSource(enum.Enum):
    TOP_LEVEL = enum.auto()
    NESTED = enum.auto()


def _fill_aligned_numerical_label(
        label: Gtk.Label,
        text: str,
) -> None:
    """Fills in a numerical label that's aligned with others of its type.

    Args:
        label: Label to fill in.
        text: Text to put in the label.
    """
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
        self._library_db = library_db
        self._playlist = playlist_
        self._in_list_box_row_activated = False
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_list.glade'),
            length=-1,
        )
        self.widget: Gtk.ListBox = builder.get_object('library_card_list')
        # TODO(dseomn): If the library is empty, show a 'Scan' button in the
        # placeholder.
        self.widget.set_placeholder(builder.get_object('empty_placeholder'))
        self.store = Gio.ListStore.new(ListItem.__gtype__)
        self.widget.bind_model(self.store, self._card)
        self.widget.connect('row-activated', self._list_box_row_activated,
                            _SignalSource.TOP_LEVEL)

    def _list_box_row_activated(
            self,
            list_box: Gtk.ListBox,
            list_box_row: ListBoxRow,
            signal_source: _SignalSource,
    ) -> None:
        """Handler for the row-activated signal."""
        del list_box  # Unused.
        # This signal seems to be triggered for all nested ListBoxRows, from
        # bottom to top. We only want to append the bottom-most one to the
        # playlist.
        already_in_list_box_row_activated = self._in_list_box_row_activated
        if signal_source is _SignalSource.TOP_LEVEL:
            self._in_list_box_row_activated = False
        else:
            self._in_list_box_row_activated = True
        if already_in_list_box_row_activated:
            return
        self._playlist.append(list_box_row.library_token)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _track(
            self,
            track: entity.Track,
            *,
            albumartist: str = '',
            show_discnumber: bool = True,
    ) -> ListBoxRow:  # yapf: disable
        """Returns a track widget."""
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_track.glade'),
            length=-1,
        )
        discnumber_widget = builder.get_object('discnumber')
        if show_discnumber:
            _fill_aligned_numerical_label(
                discnumber_widget,
                track.tags.one_or_none(tag.PARSED_DISCNUMBER) or '',
            )
        else:
            discnumber_widget.set_no_show_all(True)
            discnumber_widget.hide()
        _fill_aligned_numerical_label(
            builder.get_object('tracknumber'),
            track.tags.one_or_none(tag.PARSED_TRACKNUMBER) or '',
        )
        builder.get_object('title').set_text(track.tags.singular(tag.TITLE))
        text_direction.set_label_direction_from_text(
            builder.get_object('title'))
        artist = track.tags.singular(tag.ARTIST)
        artist_widget = builder.get_object('artist')
        if artist != albumartist:
            artist_widget.set_text(artist)
            text_direction.set_label_direction_from_text(artist_widget)
        else:
            artist_widget.set_no_show_all(True)
            artist_widget.hide()
        _fill_aligned_numerical_label(
            builder.get_object('duration'),
            track.tags.one_or_none(tag.DURATION_HUMAN) or '',
        )
        return ListBoxRow(track.token, builder.get_object('track'))

    def _medium(
            self,
            medium: entity.Medium,
            *,
            albumartist: str = '',
    ) -> ListBoxRow:
        """Returns a medium widget."""
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_medium.glade'),
            length=-1,
        )
        # TODO(dseomn): Add album information if this is not part of an album
        # card.
        header = _medium_header(medium.tags)
        header_widget = builder.get_object('header')
        if header:
            header_widget.set_text(header)
            text_direction.set_label_direction_from_text(header_widget)
        else:
            header_widget.set_no_show_all(True)
            header_widget.hide()
        tracks = builder.get_object('tracks')
        tracks.connect('row-activated', self._list_box_row_activated,
                       _SignalSource.NESTED)
        for track in medium.tracks:
            tracks.insert(self._track(track,
                                      albumartist=albumartist,
                                      show_discnumber=False),
                          position=-1)
        return ListBoxRow(medium.token, builder.get_object('medium'))

    def _album(self, album: entity.Album) -> ListBoxRow:
        """Returns an album widget."""
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_album.glade'),
            length=-1,
        )
        builder.get_object('title').set_text(album.tags.singular(tag.ALBUM))
        text_direction.set_label_direction_from_text(
            builder.get_object('title'))
        artist = album.tags.singular(tag.ALBUMARTIST, tag.ARTIST)
        builder.get_object('artist').set_text(artist)
        text_direction.set_label_direction_from_text(
            builder.get_object('artist'))
        _fill_aligned_numerical_label(
            builder.get_object('date'),
            album.tags.singular(tag.DATE, default=''),
        )
        mediums = builder.get_object('mediums')
        mediums.connect('row-activated', self._list_box_row_activated,
                        _SignalSource.NESTED)
        for medium in album.mediums:
            mediums.insert(self._medium(medium, albumartist=artist),
                           position=-1)
        return ListBoxRow(album.token, builder.get_object('album'))

    def _card(self, item: ListItem) -> ListBoxRow:
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
