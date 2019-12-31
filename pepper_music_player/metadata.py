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
import enum
from typing import Iterable, Mapping, Tuple, Union

import frozendict


class TagName(enum.Enum):
    """Name of a known tag.

    Code that needs to access specific tags (e.g., getting the track number)
    should use this enum. Code that works with arbitrary tags (e.g., running a
    user-entered query with tags specified by the user) may use str tag names
    instead.
    """
    ALBUM = 'album'
    ALBUMARTIST = 'albumartist'
    MUSICBRAINZ_ALBUMID = 'musicbrainz_albumid'


ArbitraryTagName = Union[TagName, str]


def _tag_name_str(tag_name: ArbitraryTagName) -> str:
    """Returns the str form of a tag name."""
    if isinstance(tag_name, TagName):
        return tag_name.value
    else:
        return tag_name


class Tags(frozendict.frozendict, Mapping[ArbitraryTagName, Tuple[str]]):
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

    def __getitem__(self, key: ArbitraryTagName) -> Tuple[str]:
        return super().__getitem__(_tag_name_str(key))

    def __contains__(self, key: ArbitraryTagName) -> bool:
        return super().__contains__(_tag_name_str(key))


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
        token: Opaque token that identifies this track.
        album_token: Opaque token that identifies the album for this file. If
            two files are on the same album, they should have the same token;
            otherwise, they should have different tokens. Callers should not
            rely on any other property of the token.
    """
    tags: Tags
    token: str = dataclasses.field(init=False, repr=False)
    album_token: str = dataclasses.field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            'token',
            repr((
                'track/v1alpha',  # TODO(#20): Change to v1.
                self.dirname,
                self.filename,
            )),
        )
        object.__setattr__(
            self,
            'album_token',
            repr((
                'album/v1alpha',  # TODO(#20): Change to v1.
                self.dirname,
                self.tags.get(TagName.ALBUM, ()),
                self.tags.get(TagName.ALBUMARTIST, ()),
                self.tags.get(TagName.MUSICBRAINZ_ALBUMID, ()),
            )),
        )
