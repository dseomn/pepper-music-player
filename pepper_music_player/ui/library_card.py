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
from typing import Generic, Optional, Type, TypeVar

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

    This can be either a top-level row for a card, or a nested row for a child
    entity within a card.

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


class _SignalSource(enum.Enum):
    TOP_LEVEL = enum.auto()
    NESTED = enum.auto()


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
        STYLE_CLASS_EMPTY: Style class on empty lists.
        widget: Widget showing the list.
        list_box: List widget itself.
        store: Content in the list.
    """
    STYLE_CLASS_EMPTY = 'empty'

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
        self._in_list_box_row_activated = False
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_list.glade'),
            length=-1,
        )
        self.widget: Gtk.Widget = builder.get_object(
            'library_card_list_container')
        self.list_box: Gtk.ListBox = builder.get_object('library_card_list')
        self.list_box.get_style_context().add_class(self.STYLE_CLASS_EMPTY)
        self.store = Gio.ListStore.new(list_item_type.__gtype__)
        self.store.connect('items-changed', self._items_changed_handler)
        self.list_box.set_header_func(self._header_func)
        self.list_box.bind_model(self.store, self._card)
        self.list_box.connect('row-activated', self._list_box_row_activated,
                              _SignalSource.TOP_LEVEL)

    def _header_func(
            self,
            row: ListBoxRow[ListItemType],
            before: ListBoxRow[ListItemType],
    ) -> None:
        """See Gtk.ListBoxUpdateHeaderFunc."""
        # TODO(dseomn): Figure out if there's a better way to get
        # @theme_bg_color both around the list and between rows using only CSS.
        if before and not row.get_header():
            spacer = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            spacer.get_style_context().add_class('card-spacer')
            row.set_header(spacer)
        elif not before and row.get_header():
            row.set_header(None)

    def _items_changed_handler(
            self,
            list_model: Gio.ListModel,
            position: int,
            removed: int,
            added: int,
    ) -> None:
        """See Gio.ListModel.signals.items_changed."""
        del position, removed, added  # Unused.
        if list_model.get_n_items():
            self.list_box.get_style_context().remove_class(
                self.STYLE_CLASS_EMPTY)
        else:
            self.list_box.get_style_context().add_class(self.STYLE_CLASS_EMPTY)

    def row_activated(self, row: ListBoxRow[ListItemType]) -> None:
        """Handler for a (possibly nested) row being activated.

        This exists for subclasses to override, since the default implementation
        is a noop.

        Args:
            row: The (possibly nested) row that was activated.
        """
        del row  # Unused.

    def _list_box_row_activated(
            self,
            list_box: Gtk.ListBox,
            list_box_row: ListBoxRow[ListItemType],
            signal_source: _SignalSource,
    ) -> None:
        """Handler for the row-activated signal."""
        del list_box  # Unused.
        # This signal seems to be triggered for all nested ListBoxRows, from
        # bottom to top. We only want to call row_activated for the bottom-most
        # one.
        already_in_list_box_row_activated = self._in_list_box_row_activated
        if signal_source is _SignalSource.TOP_LEVEL:
            self._in_list_box_row_activated = False
        else:
            self._in_list_box_row_activated = True
        if already_in_list_box_row_activated:
            return
        self.row_activated(list_box_row)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _track(
            self,
            list_item: ListItemType,
            track: entity.Track,
            *,
            albumartist: str = '',
            show_discnumber: bool = True,
    ) -> ListBoxRow[ListItemType]:  # yapf: disable
        """Returns a track widget."""
        builder = Gtk.Builder.new_from_string(
            resources.read_text('pepper_music_player.ui',
                                'library_card_track.glade'),
            length=-1,
        )
        discnumber_widget = builder.get_object('discnumber')
        if show_discnumber:
            alignment.fill_aligned_numerical_label(
                discnumber_widget,
                track.tags.one_or_none(tag.PARSED_DISCNUMBER) or '',
            )
        else:
            discnumber_widget.set_no_show_all(True)
            discnumber_widget.hide()
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
        return ListBoxRow(track.token, list_item, builder.get_object('track'))

    def _medium(
            self,
            list_item: ListItemType,
            medium: entity.Medium,
            *,
            albumartist: str = '',
    ) -> ListBoxRow[ListItemType]:
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
            # TODO(dseomn): Should the alignment come from the discsubtitle
            # only?
            alignment.set_label_direction_from_text(header_widget)
        else:
            header_widget.set_no_show_all(True)
            header_widget.hide()
        tracks = builder.get_object('tracks')
        tracks.connect('row-activated', self._list_box_row_activated,
                       _SignalSource.NESTED)
        for track in medium.tracks:
            tracks.insert(self._track(list_item,
                                      track,
                                      albumartist=albumartist,
                                      show_discnumber=False),
                          position=-1)
        return ListBoxRow(medium.token, list_item, builder.get_object('medium'))

    def _album(
            self,
            list_item: ListItemType,
            album: entity.Album,
    ) -> ListBoxRow[ListItemType]:
        """Returns an album widget."""
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
        mediums = builder.get_object('mediums')
        mediums.connect('row-activated', self._list_box_row_activated,
                        _SignalSource.NESTED)
        for medium in album.mediums:
            mediums.insert(self._medium(list_item, medium, albumartist=artist),
                           position=-1)
        return ListBoxRow(album.token, list_item, builder.get_object('album'))

    def _card(self, item: ListItemType) -> ListBoxRow[ListItemType]:
        """Returns a card widget for the given list item."""
        if isinstance(item.library_token, token.Track):
            return self._track(item, self._library_db.track(item.library_token))
        elif isinstance(item.library_token, token.Medium):
            return self._medium(item,
                                self._library_db.medium(item.library_token))
        elif isinstance(item.library_token, token.Album):
            return self._album(item, self._library_db.album(item.library_token))
        else:
            raise ValueError(
                f'Unknown library token type: {item.library_token}')
