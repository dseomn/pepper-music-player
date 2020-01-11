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
from typing import Tuple

from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token as metadata_token


@dataclasses.dataclass(frozen=True)
class Track:
    """A track.

    Attributes:
        tags: Tags from the track.
        token: Opaque token that identifies this track.
        album_token: Opaque token that identifies the album for this track.
    """
    tags: tag.Tags
    token: metadata_token.Track = dataclasses.field(init=False, repr=False)
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
        object.__setattr__(
            self,
            'album_token',
            metadata_token.Album(
                repr((
                    'album/v1alpha',  # TODO(#20): Change to v1.
                    self.tags.get(tag.DIRNAME, ()),
                    self.tags.get(tag.ALBUM, ()),
                    self.tags.get(tag.ALBUMARTIST, ()),
                    self.tags.get(tag.MUSICBRAINZ_ALBUMID, ()),
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
    token: metadata_token.Album = dataclasses.field(init=False, repr=False)
    tags: tag.Tags
    tracks: Tuple[Track, ...]

    def __post_init__(self) -> None:
        album_tokens = {track.album_token for track in self.tracks}
        if len(album_tokens) != 1:
            raise ValueError(
                f'Album must have exactly one token, not {album_tokens!r}')
        object.__setattr__(self, 'token', next(iter(album_tokens)))
