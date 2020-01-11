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
"""Music tags."""

import collections
import dataclasses
import functools
import operator
import re
from typing import ClassVar, Iterable, Mapping, Optional, Tuple, Union

import frozendict


@dataclasses.dataclass(frozen=True)
class Tag:
    """Information about a known tag.

    Code that needs to access specific tags (e.g., getting the track number)
    should use objects of this type. Code that works with arbitrary tags (e.g.,
    running a user-entered query with tags specified by the user) may use str
    tag names instead.

    See https://picard.musicbrainz.org/docs/tags/ for a good list of available
    tags and documentation about each one.

    Attributes:
        name: Name of the tag.
    """
    name: str


ArbitraryTag = Union[Tag, str]


@dataclasses.dataclass(frozen=True)
class PseudoTag(Tag):
    """Pseudo-tag that doesn't exist in a file's real tags.

    Attributes:
        PREFIX: Prefix that all pseudo-tags must start with.
    """
    PREFIX: ClassVar[str] = '~'

    def __post_init__(self) -> None:
        """See base class."""
        # TODO(https://github.com/google/pytype/issues/492): Remove pytype
        # disable.
        if not self.name.startswith(self.PREFIX):  # pytype: disable=wrong-arg-types
            raise ValueError(f'Tag name must start with {self.PREFIX!r}.')


ALBUM = Tag('album')
ALBUMARTIST = Tag('albumartist')
MUSICBRAINZ_ALBUMID = Tag('musicbrainz_albumid')
TRACKNUMBER = Tag('tracknumber')

BASENAME = PseudoTag('~basename')
DIRNAME = PseudoTag('~dirname')
FILENAME = PseudoTag('~filename')


def _tag_name_str(tag: ArbitraryTag) -> str:
    """Returns the str form of a tag name."""
    if isinstance(tag, Tag):
        return tag.name
    else:
        return tag


class Tags(frozendict.frozendict, Mapping[ArbitraryTag, Tuple[str]]):
    """Tags, e.g., from a file/track or album.

    Note that tags can have multiple values, potentially even multiple identical
    values. E.g., this is a valid set of tags: {'a': ('b', 'b')}
    """

    # Track number tags are typically either simple non-negative integers, or
    # they include the total number of tracks like '3/12'. This matches both
    # types.
    _TRACKNUMBER_REGEX = re.compile(
        r'(?P<tracknumber>\d+)(?:/(?P<totaltracks>\d+))?')

    def __init__(self, tags: Mapping[ArbitraryTag, Iterable[str]]) -> None:
        """Initializer.

        Args:
            tags: Tags to represent, as a mapping from each tag name to all
                values for that tag.
        """
        super().__init__({
            _tag_name_str(name): tuple(values) for name, values in tags.items()
        })

    def __getitem__(self, key: ArbitraryTag) -> Tuple[str]:
        return super().__getitem__(_tag_name_str(key))

    def __contains__(self, key: ArbitraryTag) -> bool:
        return super().__contains__(_tag_name_str(key))

    def one_or_none(self, key: ArbitraryTag) -> Optional[str]:
        """Returns a single value, or None if there isn't exactly one value."""
        values = self.get(key, ())
        if len(values) == 1:
            return values[0]
        else:
            return None

    def singular(
            self,
            key: ArbitraryTag,
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

    @property
    def tracknumber(self) -> Optional[str]:
        """The human-readable track number, if there is one."""
        tracknumber = self.one_or_none(TRACKNUMBER)
        if tracknumber is None:
            return None
        match = self._TRACKNUMBER_REGEX.fullmatch(tracknumber)
        if match is None:
            return tracknumber
        else:
            return match.group('tracknumber')


def compose(components_tags: Iterable[Tags]) -> Tags:
    """Returns the tags for an entity composed of tagged sub-entities.

    E.g., this can get the tags for an album composed of tracks. In general, the
    composite entity's tags are the intersection of its element's tags.

    Args:
        components_tags: Tags for all the components.
    """
    if not components_tags:
        return Tags({})

    tag_pair_counters = []
    for component_tags in components_tags:
        tag_pairs = []
        for name, values in component_tags.items():
            tag_pairs.extend((name, value) for value in values)
        tag_pair_counters.append(collections.Counter(tag_pairs))
    common_tag_pair_counter = functools.reduce(operator.and_, tag_pair_counters)

    tags = collections.defaultdict(list)
    for name, value in common_tag_pair_counter.elements():
        tags[name].append(value)
    return Tags(tags)
