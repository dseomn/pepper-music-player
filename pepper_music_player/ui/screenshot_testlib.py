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
"""Helpers for screenshot testing."""

import os
import pathlib
import unittest

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.ui import application


def _screenshot(
        window: Gtk.OffscreenWindow,
        filepath: pathlib.Path,
        *,
        dark_theme: bool,
        direction: Gtk.TextDirection,
) -> None:
    """Saves a screenshot of a window to a file.

    Args:
        window: Window to take a screenshot of.
        filepath: Where to save the screenshot.
        dark_theme: Whether or not to use dark theme for the window.
        direction: UI direction for the window.
    """
    old_direction = Gtk.Window.get_default_direction()
    Gtk.Window.set_default_direction(direction)
    settings = Gtk.Settings.get_default()
    # When running under Xvfb, gtk-application-prefer-dark-theme seems to have
    # no effect unless gtk-theme-name is set first.
    force_gtk_theme = os.getenv('TEST_FORCE_GTK_THEME')
    if force_gtk_theme is not None:
        settings.set_property('gtk-theme-name', force_gtk_theme)
    settings.set_property('gtk-application-prefer-dark-theme', dark_theme)
    settings.set_property('gtk-enable-animations', False)
    GLib.idle_add(Gtk.main_quit)
    Gtk.main()
    window.get_surface().write_to_png(filepath)
    settings.reset_property('gtk-theme-name')
    settings.reset_property('gtk-application-prefer-dark-theme')
    settings.reset_property('gtk-enable-animations')
    Gtk.Window.set_default_direction(old_direction)


class TestCase(unittest.TestCase):
    """Base class for screenshot testing."""

    def register_widget_screenshot(self, widget: Gtk.Widget) -> None:
        """Registers a Widget for screenshot testing.

        If the TEST_ARTIFACT_DIR environment variable is set, this will save the
        screenshot there for manual observation or external automated testing.

        This should not be called more than once from each test method, since it
        names the screenshots after the test method.

        Args:
            widget: Widget to take a screenshot of.
        """
        application.install_css()
        window = Gtk.OffscreenWindow()
        window.add(widget)
        window.show_all()
        GLib.idle_add(Gtk.main_quit)
        Gtk.main()
        artifact_dir = os.getenv('TEST_ARTIFACT_DIR')
        if artifact_dir is None:
            return
        screenshot_dir = pathlib.Path(artifact_dir).joinpath('screenshots')
        screenshot_dir.mkdir(exist_ok=True)
        _screenshot(window,
                    screenshot_dir.joinpath(f'{self.id()}.light-ltr.png'),
                    dark_theme=False,
                    direction=Gtk.TextDirection.LTR)
        _screenshot(window,
                    screenshot_dir.joinpath(f'{self.id()}.light-rtl.png'),
                    dark_theme=False,
                    direction=Gtk.TextDirection.RTL)
        _screenshot(window,
                    screenshot_dir.joinpath(f'{self.id()}.dark-ltr.png'),
                    dark_theme=True,
                    direction=Gtk.TextDirection.LTR)

    def register_narrow_widget_screenshot(self, widget: Gtk.Widget) -> None:
        """Registers a Widget that's too narrow for percy.io.

        Percy.io requires images to be between 120 and 2000 pixels wide. This
        method adds extra space around the registered widget to make it at least
        120px wide.

        Args:
            widget: Widget to take a screenshot of.
        """
        spacer = Gtk.Label.new('├─── This space intentionally left blank. ───┤')
        spacer.set_direction(Gtk.TextDirection.LTR)
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, spacing=0)
        box.add(widget)
        box.add(spacer)
        self.register_widget_screenshot(box)
