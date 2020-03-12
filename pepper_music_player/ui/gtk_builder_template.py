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
"""Templating for Gtk.Builder."""

from typing import Any

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import jinja2


class Template:
    """Gtk.Builder template.

    This is designed for building widgets that contain music metadata.
    """

    def __init__(self, template: str) -> None:
        """Initializer.

        Args:
            template: Jinja2 template of a Gtk.Builder xml file.
        """
        environment = jinja2.Environment(
            undefined=jinja2.StrictUndefined,
            autoescape=True,
        )
        self._template = environment.from_string(template)

    def render(self, **variables: Any) -> Gtk.Builder:
        """Returns the rendered template."""
        return Gtk.Builder.new_from_string(self._template.render(**variables),
                                           length=-1)
