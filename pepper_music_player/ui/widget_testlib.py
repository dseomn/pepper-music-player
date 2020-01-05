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
"""Helpers to test GTK widgets."""

import math
import os
import pathlib
import shutil
import statistics
import tempfile
import unittest

from PIL import Image
from PIL import ImageChops
from PIL import ImageOps
from PIL import ImageStat
import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pepper_music_player.ui import load


def _write_widget_to_png(widget: Gtk.Widget, path: pathlib.Path) -> None:
    """Writes the contents of a widget to a PNG image."""
    settings = Gtk.Settings.get_default()
    settings.set_property('gtk-application-prefer-dark-theme', False)
    settings.set_property('gtk-font-name', 'Arial 10')
    settings.set_property('gtk-icon-theme-name', 'Adwaita')
    settings.set_property('gtk-theme-name', 'Adwaita')
    screen = Gdk.Screen.get_default()
    screen.set_resolution(96.0)
    css = Gtk.CssProvider()
    # Adwaita changed some colors around GTK 3.24. This CSS uses the new colors
    # as needed to minimize differences between images from different GTK
    # versions. See https://blog.gtk.org/2019/01/14/theme-changes-in-gtk-3/ for
    # more details.
    css.load_from_data(b"""
        .background {
            background-color: #f6f5f4;
        }
    """)
    window = Gtk.OffscreenWindow()
    window.get_style_context().add_provider(
        css, Gtk.STYLE_PROVIDER_PRIORITY_SETTINGS)
    window.add(widget)
    window.show_all()
    GLib.idle_add(Gtk.main_quit)
    Gtk.main()
    window.get_surface().write_to_png(path)


def _rms_error(image1: Image.Image, image2: Image.Image) -> float:
    """Returns the root-mean-square error between two images."""
    rms_by_channel = ImageStat.Stat(ImageChops.difference(image1, image2)).rms
    return math.sqrt(statistics.mean(rms * rms for rms in rms_by_channel))


class WidgetTestCase(unittest.TestCase):
    """Base class for widget tests."""

    def assert_widget_matches_image(
            self,
            image_package: str,
            image_resource: str,
            widget: Gtk.Widget,
            *,
            max_rms_error: float = 30.0,
    ) -> None:
        """Asserts that a widget matches a reference image.

        Args:
            image_package: Python package with the reference image.
            image_resource: Filename of the reference image within the package.
            widget: Widget to compare to the reference image.
            max_rms_error: Maximum root-mean-square subpixel difference between
                the widget image and the reference image.
        """
        actual_dir = pathlib.Path(
            tempfile.mkdtemp(dir=os.getenv('TEST_ARTIFACT_DIR')))
        actual_path = actual_dir.joinpath(image_resource)
        _write_widget_to_png(widget, actual_path)
        actual = Image.open(actual_path)
        expected = load.image_from_resource(image_package, image_resource)
        self.assertLessEqual(
            _rms_error(expected, ImageOps.pad(actual, expected.size)),
            max_rms_error,
            f'Widget differs from reference image: {actual_path}',
        )
        # Note that this only deletes the dir if the test passes. This makes it
        # possible to manually look at the differences.
        shutil.rmtree(actual_dir)
