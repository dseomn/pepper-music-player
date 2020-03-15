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
"""Helpers for text alignment."""

from typing import TypeVar

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
gi.require_version('Pango', '1.0')
from gi.repository import Pango

WidgetType = TypeVar('WidgetType', bound=Gtk.Widget)


def _set_direction_recursive(
        widget: Gtk.Widget,
        direction: Gtk.TextDirection,
) -> None:
    widget.set_direction(direction)
    if isinstance(widget, Gtk.Container):
        widget.foreach(_set_direction_recursive, direction)


def _set_label_direction_from_text(label: Gtk.Label) -> None:
    """Sets the widget direction to match its text contents."""
    direction = Pango.find_base_dir(label.get_text(), length=-1)
    if direction is Pango.Direction.LTR:
        label.set_direction(Gtk.TextDirection.LTR)
    elif direction is Pango.Direction.RTL:
        label.set_direction(Gtk.TextDirection.RTL)


def _font_feature_tnum_attr_list() -> Pango.AttrList:
    """Returns an AttrList with font-features set to "tnum"."""
    # TODO(https://gitlab.gnome.org/GNOME/pygobject/issues/312): Delete this
    # hack once Pango 1.44.0 is available.
    return Gtk.Builder.new_from_string(
        """
            <interface>
                <object class="GtkLabel" id="label">
                    <attributes>
                        <attribute name="font-features" value="tnum" />
                    </attributes>
                </object>
            </interface>
        """,
        length=-1,
    ).get_object('label').get_attributes()


def _set_numerical_label_alignment(label: Gtk.Label) -> None:
    attributes = label.get_attributes() or Pango.AttrList()
    attributes.splice(_font_feature_tnum_attr_list(), 0, 0)
    label.set_attributes(attributes)
    # https://material.io/design/usability/bidirectionality.html says that
    # numbers should be LTR.
    label.set_direction(Gtk.TextDirection.LTR)


def _hide_label_if_empty(label: Gtk.Label) -> None:
    if not label.get_text():
        label.set_no_show_all(True)
        label.hide()


def auto_align(widget: WidgetType) -> WidgetType:
    """Recursively, automatically aligns the given widget and its children.

    This makes it possible to specify alignment in Gtk.Builder xml, instead of
    in code. The following style classes are supported:
        direction-ltr: Recursively sets the direction to LTR. This should be
            used with care, since it's generally not a good idea to override the
            user's chosen direction. However, it's needed sometimes for UI
            elements that explicitly do not follow text direction. E.g.,
            https://material.io/design/usability/bidirectionality.html#mirroring-elements
            says that "media controls for playback are always LTR."
        direction-rtl: See direction-ltr.
        direction-auto: (Gtk.Label) Sets the direction based on the text.
        numerical: (Gtk.Label) Sets the direction and alignment appropriately
            for a numerical label.
        hide-if-empty: (Gtk.Label) Hides the label if it's empty.

    Args:
        widget: Widget to automatically align.

    Returns:
        The widget.
    """
    for style_class in widget.get_style_context().list_classes():
        if style_class == 'direction-ltr':
            _set_direction_recursive(widget, Gtk.TextDirection.LTR)
        elif style_class == 'direction-rtl':
            _set_direction_recursive(widget, Gtk.TextDirection.RTL)
        elif style_class == 'direction-auto' and isinstance(widget, Gtk.Label):
            _set_label_direction_from_text(widget)
        elif style_class == 'numerical' and isinstance(widget, Gtk.Label):
            _set_numerical_label_alignment(widget)
        elif style_class == 'hide-if-empty' and isinstance(widget, Gtk.Label):
            _hide_label_if_empty(widget)
    if isinstance(widget, Gtk.Container):
        widget.foreach(auto_align)
    return widget
