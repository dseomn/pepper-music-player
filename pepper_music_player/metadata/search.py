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
"""Search queries."""

import enum


class Order(enum.Enum):
    """Orders to return search results in.

    Attributes:
        NATURAL: Natural order of entities within a common ancestor entity.
            E.g., this defines the tracklist order between tracks and mediums on
            the same album, but does not define an order between albums.
        RANDOM: A new random order each time it's used.
    """
    # TODO(dseomn): Add orders at the album-level, e.g., ALBUM_DATE to sort
    # albums by the date common to all tracks on the album, or ALBUM_ARTIST to
    # sort by the albumartist (falling back to artist) tags. Then orders could
    # be combined, e.g., (ALBUM_ARTIST, ALBUM_DATE, NATURAL).
    # TODO(dseomn): Add RELEVANCE, to be used as the first order in unstructured
    # search queries.
    NATURAL = enum.auto()
    RANDOM = enum.auto()
