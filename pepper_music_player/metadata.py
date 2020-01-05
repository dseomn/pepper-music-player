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
from typing import Iterable, Mapping, Optional, Tuple, Union

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
    """Tags, e.g., from a file/track or album.

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

    def one_or_none(self, key: ArbitraryTagName) -> Optional[str]:
        """Returns a single value, or None if there isn't exactly one value."""
        values = self.get(key, ())
        if len(values) == 1:
            return values[0]
        else:
            return None

    def singular(
            self,
            key: ArbitraryTagName,
            *,
            default: str = '[unknown]',
            separator: str = '; ',
    ) -> str:
        """Returns a single value that represents all of the tag's values.

        Args:
            key: Which tag to look up.
            default: What to return if there are no values.
            separator: What to put between values if there is more than one
                value.
        """
        return separator.join(self.get(key, (default,)))


@dataclasses.dataclass(frozen=True)
class Token:
    """Base class for opaque tokens.

    These are meant to uniquely identify things; do not rely on any other
    property of them.
    """
    _token: str

    def __str__(self) -> str:
        """See base class."""
        return self._token


@dataclasses.dataclass(frozen=True)
class TrackToken(Token):
    """Opaque token for a track."""


@dataclasses.dataclass(frozen=True)
class AlbumToken(Token):
    """Opaque token for an album."""


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

    Currently, audio files and tracks are treated as equivalent, so this class
    represents both concepts as a single entity. However, if we ever add support
    for single-file albums with embedded CUE sheets
    https://en.wikipedia.org/wiki/Cue_sheet_(computing)#Audio_file_playback, the
    concepts will need to be split apart. To hopefully ease that transition,
    code and docs should refer to these objects as tracks whenever they are
    conceptually dealing with tracks instead of files. E.g., the filename and
    dirname attributes are conceptually about the file, but the token attribute
    is about the track.

    Attributes:
        tags: Tags from the audio file.
        token: Opaque token that identifies this track.
        album_token: Opaque token that identifies the album for this track.
    """
    tags: Tags
    token: TrackToken = dataclasses.field(init=False, repr=False)
    album_token: AlbumToken = dataclasses.field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            'token',
            TrackToken(
                repr((
                    'track/v1alpha',  # TODO(#20): Change to v1.
                    self.dirname,
                    self.filename,
                ))),
        )
        object.__setattr__(
            self,
            'album_token',
            AlbumToken(
                repr((
                    'album/v1alpha',  # TODO(#20): Change to v1.
                    self.dirname,
                    self.tags.get(TagName.ALBUM, ()),
                    self.tags.get(TagName.ALBUMARTIST, ()),
                    self.tags.get(TagName.MUSICBRAINZ_ALBUMID, ()),
                ))),
        )


@dataclasses.dataclass(frozen=True)
class Album:
    """An album.

    Attributes:
        token: Opaque token that identifies this album.
        tags: Tags that are common to all tracks on the album.
        tracks: Tracks on the album.
    """
    token: AlbumToken = dataclasses.field(init=False, repr=False)
    tags: Tags
    tracks: Tuple[AudioFile]

    def __post_init__(self) -> None:
        album_tokens = {track.album_token for track in self.tracks}
        if len(album_tokens) != 1:
            raise ValueError(
                f'Album must have exactly one token, not {album_tokens!r}')
        object.__setattr__(self, 'token', next(iter(album_tokens)))
