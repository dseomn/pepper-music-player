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

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('GObject', '2.0')
from gi.repository import GObject
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


class WidgetFactory:
    """Factory to create library card widgets."""

    def __init__(self, library_db: database.Database):
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

    def _track(self, track: entity.Track) -> Gtk.Widget:
        """Returns a track widget."""
        builder = load.builder_from_resource('pepper_music_player.ui',
                                             'library_card_track.glade')
        # TODO(dseomn): Show a blank discnumber if it's part of a Medium
        # widget.
        _fill_aligned_numerical_label(
            builder.get_object('discnumber'),
            self._discnumber_size_group,
            track.tags.one_or_none(tag.PARSED_DISCNUMBER) or '',
        )
        _fill_aligned_numerical_label(
            builder.get_object('tracknumber'),
            self._tracknumber_size_group,
            track.tags.one_or_none(tag.PARSED_TRACKNUMBER) or '',
        )
        # TODO(https://discourse.gnome.org/t/is-there-any-way-to-align-a-gtklabel-at-the-horizontal-start-based-on-text-direction/2429):
        # Align RTL text correctly.
        builder.get_object('title').set_text(track.tags.singular(tag.TITLE))
        # TODO(dseomn): Don't show the artist if it's part of an Album widget
        # and the artist is the same as the albumartist.
        builder.get_object('artist').set_text(track.tags.singular(tag.ARTIST))
        _fill_aligned_numerical_label(
            builder.get_object('duration'),
            self._duration_size_group,
            track.tags.one_or_none(tag.DURATION_HUMAN) or '',
        )
        return builder.get_object('track_card')

    def build(self, item: ListItem) -> Gtk.Widget:
        """Returns a card widget for the given list item."""
        # TODO(dseomn): Add card types for Albums and Mediums.
        if isinstance(item.library_token, token.Track):
            return self._track(self._library_db.track(item.library_token))
        else:
            raise ValueError(
                f'Unknown library token type: {item.library_token}')
