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
from typing import Generator, Iterable, Tuple

import mutagen

from pepper_music_player import metadata


def _read_tags(filename: str) -> Iterable[Tuple[str, str]]:
    """Reads tags from a file.

    Args:
        filename: Where to read tags from.

    Returns:
        See the tags attribute of metadata.AudioFile.
    """
    file_info = mutagen.File(filename, easy=True)
    if file_info.tags is None:
        return ()
    tags_list = []
    for key, values in file_info.tags.items():
        for value in values:
            tags_list.append((key, value))
    # sorted() is used to make testing easier.
    return tuple(sorted(tags_list))


def scan(root_dirname: str) -> Generator[metadata.File, None, None]:
    """Scans a directory."""
    # TODO: Keep track of errors with os.walk(onerror=...)
    # TODO: Catch and handle per-file errors.
    for dirname, _, filenames in os.walk(os.path.abspath(root_dirname)):
        dirpath = pathlib.Path(dirname)
        for filename in filenames:
            filepath = dirpath.joinpath(filename)
            mime, _ = mimetypes.guess_type(filepath.as_uri())
            mime_major, _, _ = (mime or '').partition('/')
            if mime_major == 'audio':
                yield metadata.AudioFile(dirname=dirname,
                                         filename=filename,
                                         tags=_read_tags(str(filepath)))
            else:
                yield metadata.File(dirname=dirname, filename=filename)
