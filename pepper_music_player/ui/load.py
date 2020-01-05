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
"""Helpers to load data from python resources."""

import io
import pkgutil

from PIL import Image
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


def _load(package: str, resource: str) -> bytes:
    resource_bytes = pkgutil.get_data(package, resource)
    if resource_bytes is None:
        raise RuntimeError("The package loader doesn't support get_data().")
    return resource_bytes


def builder_from_resource(package: str, resource: str) -> Gtk.Builder:
    """Returns a builder from a python resource.

    Args:
        package: Package to load from, e.g., 'pepper_music_player.ui'.
        resource: Filename within the package.
    """
    builder = Gtk.Builder()
    builder.add_from_string(_load(package, resource).decode())
    return builder


def image_from_resource(package: str, resource: str) -> Image.Image:
    """Returns an image from a python resource.

    Args:
        package: Package to load from, e.g., 'pepper_music_player.ui'.
        resource: Filename within the package.
    """
    return Image.open(io.BytesIO(_load(package, resource)))
