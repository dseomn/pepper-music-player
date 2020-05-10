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
import logging
from typing import Iterable, Sequence
import uuid

from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token as metadata_token


def _token_str(
        *,
        token_type: str,
        token_version: str,
        data: str,
) -> str:
    """Returns a token string.

    Args:
        token_type: What this token is for.
        token_version: Version of this token. If the token string changes for
            the same entity, this should change too.
        data: Contents of the token.
    """
    return f'{token_type}/{token_version}:{data}'


def _tag_token_str(
        token_type: str,
        token_version: str,
        tag_data: tag.Tags,
        *token_tags: tag.Tag,
) -> str:
    """Returns a token string from tags.

    This function should minimize the situations in which token_version has to
    change, by allowing as many code changes as possible without affecting
    existing tokens. E.g., it includes the tag names so that a track token based
    on the filename can stay valid if we later add track tokens based on
    streaming URLs in additon.

    Args:
        token_type: See _token_str().
        token_version: See _token_str().
        tag_data: Tags to get data from for the token.
        *token_tags: Which tags go into the token.
    """
    token_tag_pairs = []
    for token_tag in token_tags:
        token_tag_pairs.extend(
            (token_tag.name, value) for value in tag_data.get(token_tag, ()))
    return _token_str(
        token_type=token_type,
        token_version=token_version,
        data=repr(tuple(token_tag_pairs)),
    )


def _sort_key(version: int, tag_data: tag.Tags, *int_tags: tag.Tag) -> bytes:
    """Returns a sort key from integer values.

    Args:
        version: Version of the sort key.
        tag_data: Tags to get data from for the sort key.
        int_tags: Single-valued tags with integer values to use in the sort key.
            Earlier tags are more significant.
    """
    components = [version.to_bytes(1, 'big')]
    for int_tag in int_tags:
        try:
            tag_bytes = (tag_data.int_or_none(int_tag) or 0).to_bytes(8, 'big')
        except OverflowError:
            logging.exception('Invalid tag for sort key: %s=%r', int_tag.name,
                              tag_data[int_tag])
            tag_bytes = (0).to_bytes(8, 'big')
        components.append(tag_bytes)
    return b''.join(components)


@dataclasses.dataclass(frozen=True)
class Track:
    """A track.

    Attributes:
        tags: Tags from the track.
        token: Opaque token that identifies this track.
        medium_token: Opaque token that identifies the medium for this track.
        album_token: Opaque token that identifies the album for this track.
        sort_key: Key for sorting this track within its album. Note that this is
            not guaranteed to be unique.
        medium_sort_key: Key for sorting this track's medium within its album.
            This is also not guaranteed to be unique.
    """
    tags: tag.Tags = dataclasses.field(repr=False)
    token: metadata_token.Track = dataclasses.field(init=False)
    medium_token: metadata_token.Medium = dataclasses.field(init=False,
                                                            repr=False)
    album_token: metadata_token.Album = dataclasses.field(init=False,
                                                          repr=False)
    sort_key: bytes = dataclasses.field(init=False)
    medium_sort_key: bytes = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        # TODO(#20): Change versions to v1.
        object.__setattr__(
            self, 'token',
            metadata_token.Track(
                _tag_token_str('track', 'v1alpha', self.tags, tag.FILENAME)))
        album_token_tags = (
            tag.DIRNAME,
            tag.ALBUM,
            tag.ALBUMARTIST,
            tag.MUSICBRAINZ_ALBUMID,
        )
        object.__setattr__(
            self, 'medium_token',
            metadata_token.Medium(
                _tag_token_str('medium', 'v1alpha', self.tags,
                               *album_token_tags, tag.PARSED_DISCNUMBER)))
        object.__setattr__(
            self, 'album_token',
            metadata_token.Album(
                _tag_token_str('album', 'v1alpha', self.tags,
                               *album_token_tags)))
        object.__setattr__(
            self,
            'sort_key',
            _sort_key(0, self.tags, tag.PARSED_DISCNUMBER,
                      tag.PARSED_TRACKNUMBER),
        )
        object.__setattr__(
            self,
            'medium_sort_key',
            _sort_key(0, self.tags, tag.PARSED_DISCNUMBER),
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
        tracks: Tracks on this medium.
    """
    tags: tag.Tags = dataclasses.field(repr=False)
    token: metadata_token.Medium = dataclasses.field(init=False)
    album_token: metadata_token.Album = dataclasses.field(init=False,
                                                          repr=False)
    tracks: Sequence[Track] = dataclasses.field(repr=False)

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
    mediums: Sequence[Medium] = dataclasses.field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'token',
            _require_one_token(medium.album_token for medium in self.mediums))


def _playlist_entry_token() -> metadata_token.PlaylistEntry:
    # TODO(#20): Change version to v1.
    return metadata_token.PlaylistEntry(
        _token_str(
            token_type='playlistEntry',
            token_version='v1alpha',
            data=str(uuid.uuid4()),
        ))


@dataclasses.dataclass(frozen=True)
class PlaylistEntry:
    """An entry in the playlist.

    Attributes:
        library_token: Token of the library entity for this playlist entry.
        token: Token of the entry.
    """
    library_token: metadata_token.LibraryToken
    token: metadata_token.PlaylistEntry = dataclasses.field(
        default_factory=_playlist_entry_token)


@dataclasses.dataclass(frozen=True)
class PlayableUnit:
    """The minimal unit that a player can play, i.e., a track.

    Attributes:
        playlist_entry: Where the track is in the playlist.
        track: The track to play.
    """
    playlist_entry: PlaylistEntry
    track: Track
