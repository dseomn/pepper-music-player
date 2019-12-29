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
"""Metadata about files, tracks, albums, etc.

In general, all the metadata classes in this file should be read-only (e.g.,
tuples instead of lists) because: 1) It can prevent bugs if some code
accidentally tries to modify a shared piece of metadata. 2) It makes sharing
metadata across threads easier.
"""

import dataclasses
from typing import Iterable, Mapping, Tuple

import frozendict


class Tags(frozendict.frozendict, Mapping[str, Tuple[str]]):
    """Tags, typically from an audio file.

    Note that tags can have multiple values, potentially even multiple identical
    values. E.g., this is a valid set of tags: {'a': ('b', 'b')}
    """

    def __init__(self, tags: Mapping[str, Iterable[str]]) -> None:
        """Initializer.

        Args:
            tags: Tags to represent, as a mapping from each tag name to all
                values for that tag.
        """
        super().__init__({name: tuple(values) for name, values in tags.items()})


@dataclasses.dataclass(frozen=True)
class File:
    """A file in the music library.

    Attributes:
        dirname: Absolute name of the directory containing the file.
        filename: Name of the file, relative to dirname.
    """
    dirname: str
    filename: str


@dataclasses.dataclass(frozen=True)
class AudioFile(File):
    """An audio file.

    Attributes:
        tags: Tags from the audio file.
    """
    tags: Tags
