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
"""Entities with metadata, e.g., tracks and albums."""

import dataclasses
from typing import Iterable, Tuple

from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token as metadata_token


@dataclasses.dataclass(frozen=True)
class Track:
    """A track.

    Attributes:
        tags: Tags from the track.
        token: Opaque token that identifies this track.
        medium_token: Opaque token that identifies the medium for this track.
        album_token: Opaque token that identifies the album for this track.
    """
    tags: tag.Tags = dataclasses.field(repr=False)
    token: metadata_token.Track = dataclasses.field(init=False)
    medium_token: metadata_token.Medium = dataclasses.field(init=False,
                                                            repr=False)
    album_token: metadata_token.Album = dataclasses.field(init=False,
                                                          repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            'token',
            metadata_token.Track(
                repr((
                    'track/v1alpha',  # TODO(#20): Change to v1.
                    self.tags.get(tag.FILENAME, ()),
                ))),
        )
        album_token_fields = (
            self.tags.get(tag.DIRNAME, ()),
            self.tags.get(tag.ALBUM, ()),
            self.tags.get(tag.ALBUMARTIST, ()),
            self.tags.get(tag.MUSICBRAINZ_ALBUMID, ()),
        )
        object.__setattr__(
            self,
            'medium_token',
            metadata_token.Medium(
                repr((
                    'medium/v1alpha',  # TODO(#20): Change to v1.
                    *album_token_fields,
                    self.tags.get(tag.PARSED_DISCNUMBER, ()),
                ))),
        )
        object.__setattr__(
            self,
            'album_token',
            metadata_token.Album(
                repr((
                    'album/v1alpha',  # TODO(#20): Change to v1.
                    *album_token_fields,
                ))),
        )


# TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
def _require_one_token(
        tokens: Iterable[metadata_token.AnyLibraryToken],
) -> metadata_token.AnyLibraryToken:  # yapf: disable
    tokens_set = frozenset(tokens)
    if len(tokens_set) != 1:
        raise ValueError(
            'Entity must have exactly one token, not {tokens_set!r}')
    return next(iter(tokens_set))


@dataclasses.dataclass(frozen=True)
class Medium:
    """A medium, e.g., a disc or tape.

    Attributes:
        tags: Tags that are common to all tracks on the medium.
        token: Opaque token that identifies this medium.
        album_token: Opaque token that identifies the album for this medium.
    """
    tags: tag.Tags = dataclasses.field(repr=False)
    token: metadata_token.Medium = dataclasses.field(init=False)
    album_token: metadata_token.Album = dataclasses.field(init=False,
                                                          repr=False)
    tracks: Tuple[Track, ...] = dataclasses.field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'token',
            _require_one_token(track.medium_token for track in self.tracks))
        object.__setattr__(
            self, 'album_token',
            _require_one_token(track.album_token for track in self.tracks))


@dataclasses.dataclass(frozen=True)
class Album:
    """An album.

    Attributes:
        tags: Tags that are common to all mediums on the album.
        token: Opaque token that identifies this album.
        mediums: Mediums on the album.
    """
    tags: tag.Tags = dataclasses.field(repr=False)
    token: metadata_token.Album = dataclasses.field(init=False)
    mediums: Tuple[Medium, ...] = dataclasses.field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'token',
            _require_one_token(medium.album_token for medium in self.mediums))
