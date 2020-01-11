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
                    self.dirname,
                    self.filename,
                ))),
        )
        object.__setattr__(
            self,
            'album_token',
            metadata_token.Album(
                repr((
                    'album/v1alpha',  # TODO(#20): Change to v1.
                    self.dirname,
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
    tracks: Tuple[AudioFile]

    def __post_init__(self) -> None:
        album_tokens = {track.album_token for track in self.tracks}
        if len(album_tokens) != 1:
            raise ValueError(
                f'Album must have exactly one token, not {album_tokens!r}')
        object.__setattr__(self, 'token', next(iter(album_tokens)))
