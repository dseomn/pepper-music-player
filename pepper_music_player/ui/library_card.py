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

from importlib import resources
from typing import Generic, Iterable, Optional, Type, TypeVar

import gi
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
from pepper_music_player.ui import alignment


class ListItem(GObject.Object):
    """Data for use in a Gio.ListStore that represents library cards.

    Attributes:
        library_token: Which thing in the library to show a card for.
    """

    def __init__(self, library_token: token.LibraryToken) -> None:
        super().__init__()
        self.library_token = library_token


ListItemType = TypeVar('ListItemType', bound=ListItem)


class ListBoxRow(Gtk.ListBoxRow, Generic[ListItemType]):
    """Row that represents a library entity in a ListBox.

    These are inner rows within the list within each card, not the outer rows
    that represent entire cards.

    Attributes:
        library_token: Which thing in the library this row shows.
        list_item: List item associated with the top-level ancestor row.
    """

    def __init__(
            self,
            library_token: token.LibraryToken,
            list_item: ListItemType,
            child: Gtk.Widget,
    ) -> None:
        super().__init__()
        self.library_token = library_token
        self.list_item = list_item
        self.add(child)
        self.get_style_context().add_class('card-inner-row')
        if isinstance(self.library_token, token.Track):
            self.get_style_context().add_class('card-inner-row-track')
        elif isinstance(self.library_token, token.Medium):
            self.get_style_context().add_class('card-inner-row-medium')
        elif isinstance(self.library_token, token.Album):
            self.get_style_context().add_class('card-inner-row-album')


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


class List(Generic[ListItemType]):
    """List of library cards.

    This list just shows the cards; see subclasses for the cards' behavior.

    Attributes:
        widget: Widget showing the list.
        store: Content in the list.
    """

    def __init__(
            self,
            library_db: database.Database,
            list_item_type: Type[ListItemType] = ListItem,
    ) -> None:
        """Initializer.

        Args:
            library_db: Library database.
            list_item_type: Type of list item in the list.
        """
        self._library_db = library_db
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_outer_list.glade'),
            length=-1,
        )
        self.widget: Gtk.ListBox = builder.get_object('list')
        self.store = Gio.ListStore.new(list_item_type.__gtype__)
        self.widget.bind_model(self.store, self._card)

    def row_activated(self, row: ListBoxRow[ListItemType]) -> None:
        """Handler for an inner row being activated.

        This exists for subclasses to override, since the default implementation
        is a noop.

        Args:
            row: The inner row that was activated.
        """
        del row  # Unused.

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _track(
            self,
            list_item: ListItemType,
            track: entity.Track,
            *,
            albumartist: str = '',
            show_discnumber: bool = True,
    ) -> Iterable[ListBoxRow[ListItemType]]:  # yapf: disable
        """Yields the inner row for a track."""
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_track.glade'),
            length=-1,
        )
        if show_discnumber:
            alignment.fill_aligned_numerical_label(
                builder.get_object('discnumber'),
                track.tags.one_or_none(tag.PARSED_DISCNUMBER) or '',
            )
        alignment.fill_aligned_numerical_label(
            builder.get_object('tracknumber'),
            track.tags.one_or_none(tag.PARSED_TRACKNUMBER) or '',
        )
        builder.get_object('title').set_text(track.tags.singular(tag.TITLE))
        alignment.set_label_direction_from_text(builder.get_object('title'))
        artist = track.tags.singular(tag.ARTIST)
        artist_widget = builder.get_object('artist')
        if artist != albumartist:
            artist_widget.set_text(artist)
            alignment.set_label_direction_from_text(artist_widget)
        else:
            artist_widget.set_no_show_all(True)
            artist_widget.hide()
        alignment.fill_aligned_numerical_label(
            builder.get_object('duration'),
            track.tags.one_or_none(tag.DURATION_HUMAN) or '',
        )
        yield ListBoxRow(track.token, list_item, builder.get_object('track'))

    def _medium(
            self,
            list_item: ListItemType,
            medium: entity.Medium,
            *,
            albumartist: str = '',
    ) -> Iterable[ListBoxRow[ListItemType]]:
        """Yields inner rows for a medium."""
        # TODO(dseomn): Add album information if this is not part of an album
        # card.
        header = _medium_header(medium.tags)
        if header:
            builder = Gtk.Builder.new_from_string(
                resources.read_text('pepper_music_player.ui',
                                    'library_card_medium.glade'),
                length=-1,
            )
            header_widget = builder.get_object('header')
            header_widget.set_text(header)
            # TODO(dseomn): Should the alignment come from the discsubtitle
            # only?
            alignment.set_label_direction_from_text(header_widget)
            yield ListBoxRow(medium.token, list_item, header_widget)
        for track in medium.tracks:
            yield from self._track(list_item,
                                   track,
                                   albumartist=albumartist,
                                   show_discnumber=False)

    def _album(
            self,
            list_item: ListItemType,
            album: entity.Album,
    ) -> Iterable[ListBoxRow[ListItemType]]:
        """Yields inner rows for an album."""
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_album.glade'),
            length=-1,
        )
        builder.get_object('title').set_text(album.tags.singular(tag.ALBUM))
        alignment.set_label_direction_from_text(builder.get_object('title'))
        artist = album.tags.singular(tag.ALBUMARTIST, tag.ARTIST)
        builder.get_object('artist').set_text(artist)
        alignment.set_label_direction_from_text(builder.get_object('artist'))
        alignment.fill_aligned_numerical_label(
            builder.get_object('date'),
            album.tags.singular(tag.DATE, default=''),
        )
        yield ListBoxRow(album.token, list_item, builder.get_object('header'))
        for medium in album.mediums:
            yield from self._medium(list_item, medium, albumartist=artist)

    def _card(self, item: ListItemType) -> Gtk.ListBoxRow:
        """Returns a card outer row for the given list item."""
        if isinstance(item.library_token, token.Track):
            inner_rows = self._track(item,
                                     self._library_db.track(item.library_token))
        elif isinstance(item.library_token, token.Medium):
            inner_rows = self._medium(
                item, self._library_db.medium(item.library_token))
        elif isinstance(item.library_token, token.Album):
            inner_rows = self._album(item,
                                     self._library_db.album(item.library_token))
        else:
            raise ValueError(
                f'Unknown library token type: {item.library_token}')
        inner_list = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_inner_list.glade'),
            length=-1,
        ).get_object('list')
        inner_list.connect('row-activated',
                           lambda list_box, row: self.row_activated(row))
        for inner_row in inner_rows:
            inner_list.insert(inner_row, position=-1)
        row = Gtk.ListBoxRow()
        row.add(inner_list)
        row.show_all()
        row.set_activatable(False)
        return row
