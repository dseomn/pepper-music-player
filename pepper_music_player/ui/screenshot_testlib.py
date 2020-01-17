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
) -> None:
    """Saves a screenshot of a window to a file.

    Args:
        window: Window to take a screenshot of.
        filepath: Where to save the screenshot.
        dark_theme: Whether or not to use dark theme for the window.
    """
    settings = Gtk.Settings.get_default()
    # When running under Xvfb, gtk-application-prefer-dark-theme seems to have
    # no effect unless gtk-theme-name is set first.
    force_gtk_theme = os.getenv('TEST_FORCE_GTK_THEME')
    if force_gtk_theme is not None:
        settings.set_property('gtk-theme-name', force_gtk_theme)
    settings.set_property('gtk-application-prefer-dark-theme', dark_theme)
    GLib.idle_add(Gtk.main_quit)
    Gtk.main()
    window.get_surface().write_to_png(filepath)
    settings.reset_property('gtk-theme-name')
    settings.reset_property('gtk-application-prefer-dark-theme')


def register_widget(
        module_name: str,
        screenshot_name: str,
        widget: Gtk.Widget,
) -> None:
    """Registers a Widget for screenshot testing.

    If the TEST_ARTIFACT_DIR environment variable is set, this will save the
    screenshot there for manual observation or external automated testing.

    Args:
        module_name: Module that the test widget comes from, i.e., __name__.
        screenshot_name: A unique name for the screenshot within the test
            module.
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
    _screenshot(
        window,
        screenshot_dir.joinpath(f'{module_name}.{screenshot_name}.light.png'),
        dark_theme=False)
    _screenshot(
        window,
        screenshot_dir.joinpath(f'{module_name}.{screenshot_name}.dark.png'),
        dark_theme=True)
