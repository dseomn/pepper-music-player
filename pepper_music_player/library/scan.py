# Copyright 2019 Google LLC
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
"""Scanning code to find music in a library."""

import mimetypes
import os
import pathlib
from typing import Generator

import mutagen

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag


def _read_tags(filename: str) -> tag.Tags:
    """Returns tags read from a file."""
    file_info = mutagen.File(filename, easy=True)
    if file_info.tags is None:
        return tag.Tags({})
    return tag.Tags(file_info.tags)


def scan(root_dirname: str) -> Generator[entity.File, None, None]:
    """Scans a directory."""
    # TODO: Keep track of errors with os.walk(onerror=...)
    # TODO: Catch and handle per-file errors.
    for dirname, _, basenames in os.walk(os.path.abspath(root_dirname)):
        dirpath = pathlib.Path(dirname)
        for basename in basenames:
            filepath = dirpath.joinpath(basename)
            mime, _ = mimetypes.guess_type(filepath.as_uri())
            mime_major, _, _ = (mime or '').partition('/')
            if mime_major == 'audio':
                yield entity.AudioFile(dirname=dirname,
                                       basename=basename,
                                       tags=_read_tags(str(filepath)))
            else:
                yield entity.File(dirname=dirname, basename=basename)
