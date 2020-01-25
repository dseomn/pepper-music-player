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
"""Opaque tokens to uniquely identify things."""

import dataclasses
from typing import TypeVar


@dataclasses.dataclass(frozen=True)
class Token:
    """Base class for opaque tokens."""
    _token: str

    def __str__(self) -> str:
        """See base class."""
        return self._token


@dataclasses.dataclass(frozen=True)
class LibraryToken(Token):
    """Base class for tokens of things in the library."""


AnyLibraryToken = TypeVar('AnyLibraryToken', bound=LibraryToken)


@dataclasses.dataclass(frozen=True)
class Track(LibraryToken):
    """Opaque token for a track."""


@dataclasses.dataclass(frozen=True)
class Medium(LibraryToken):
    """Opaque token for a medium, e.g., a disc or tape."""


@dataclasses.dataclass(frozen=True)
class Album(LibraryToken):
    """Opaque token for an album."""


@dataclasses.dataclass(frozen=True)
class PlaylistEntry(Token):
    """Opaque token for an entry in a playlist."""
