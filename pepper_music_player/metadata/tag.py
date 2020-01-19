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

import abc
import collections
import dataclasses
import functools
import math
import operator
import re
from typing import ClassVar, Dict, Iterable, Mapping, Optional, Pattern, Tuple, Union

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


@dataclasses.dataclass(frozen=True)
class DerivedTag(PseudoTag, abc.ABC):
    """Pseudo-tag that is derived from other tags."""

    @abc.abstractmethod
    def derive(self, tags: 'Tags') -> Optional[Tuple[str, ...]]:
        """Derives the values for this tag.

        Args:
            tags: Tags to derive the values for this tag from.

        Returns:
            The values for this tag, or None if the tag shouldn't be included.
        """
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True)
class DurationHumanTag(DerivedTag):
    """Tag deriving a human-readable duration.

    Attributes:
        seconds_tag: Tag containing a number of seconds as a float.
    """
    seconds_tag: Tag

    def derive(self, tags: 'Tags') -> Optional[Tuple[str, ...]]:
        """See base class."""
        seconds_str = tags.one_or_none(self.seconds_tag)
        if seconds_str is None:
            return None
        try:
            total_seconds = round(float(seconds_str))
        except ValueError:
            return None
        if total_seconds < 0:
            return None
        hours, hours_remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(hours_remainder, 60)
        if hours:
            return (f'{hours}∶{minutes:02}∶{seconds:02}',)
        else:
            return (f'{minutes}∶{seconds:02}',)


@dataclasses.dataclass(frozen=True)
class IndexOrTotalTag(DerivedTag):
    """Tag deriving its value from index- and total-style tags.

    E.g., there are a couple ways to represent the track number and the total
    number of tracks on a disc. This class is for derived tags that parse those
    real tags.

    Attributes:
        is_index: True for deriving the index, False for the total.
        composite_tag: Tag of the form 'index' or 'index/total' to parse.
        plain_tags: Tags that contain only the intended values.
    """
    _COMPOSITE_REGEX: ClassVar[Pattern[str]] = re.compile(
        r'(?P<index>\d+)(?:/(?P<total>\d+))?')
    is_index: bool
    composite_tag: Tag
    plain_tags: Tuple[Tag, ...] = ()

    def derive(self, tags: 'Tags') -> Optional[Tuple[str, ...]]:
        """See base class."""
        for tag in self.plain_tags:
            if tag in tags:
                return tags[tag]
        composite_value = tags.one_or_none(self.composite_tag)
        if composite_value is None:
            return None
        # TODO(https://github.com/google/pytype/issues/492): Remove pytype
        # disable.
        composite_match = self._COMPOSITE_REGEX.fullmatch(composite_value)  # pytype: disable=attribute-error
        if composite_match is None:
            return (composite_value,) if self.is_index else None
        matched_value = composite_match.group(
            'index' if self.is_index else 'total')
        return None if matched_value is None else (matched_value,)


ALBUM = Tag('album')
ALBUMARTIST = Tag('albumartist')
ARTIST = Tag('artist')
DISCNUMBER = Tag('discnumber')  # Prefer PARSED_DISCNUMBER below.
DISCTOTAL = Tag('disctotal')  # Prefer PARSED_TOTALDISCS below.
DISCSUBTITLE = Tag('discsubtitle')
MEDIA = Tag('media')
MUSICBRAINZ_ALBUMID = Tag('musicbrainz_albumid')
TITLE = Tag('title')
TOTALDISCS = Tag('totaldiscs')  # Prefer PARSED_TOTALDISCS below.
TOTALTRACKS = Tag('totaltracks')  # Prefer PARSED_TOTALTRACKS below.
TRACKNUMBER = Tag('tracknumber')  # Prefer PARSED_TRACKNUMBER below.
TRACKTOTAL = Tag('tracktotal')  # Prefer PARSED_TOTALTRACKS below.

BASENAME = PseudoTag('~basename')
DIRNAME = PseudoTag('~dirname')
DURATION_SECONDS = PseudoTag('~duration_seconds')
FILENAME = PseudoTag('~filename')

DURATION_HUMAN = DurationHumanTag('~duration_human',
                                  seconds_tag=DURATION_SECONDS)
PARSED_DISCNUMBER = IndexOrTotalTag('~parsed_discnumber',
                                    is_index=True,
                                    composite_tag=DISCNUMBER)
PARSED_TOTALDISCS = IndexOrTotalTag('~parsed_totaldiscs',
                                    is_index=False,
                                    composite_tag=DISCNUMBER,
                                    plain_tags=(TOTALDISCS, DISCTOTAL))
PARSED_TOTALTRACKS = IndexOrTotalTag('~parsed_totaltracks',
                                     is_index=False,
                                     composite_tag=TRACKNUMBER,
                                     plain_tags=(TOTALTRACKS, TRACKTOTAL))
PARSED_TRACKNUMBER = IndexOrTotalTag('~parsed_tracknumber',
                                     is_index=True,
                                     composite_tag=TRACKNUMBER)

_DERIVED_TAGS = (
    DURATION_HUMAN,
    PARSED_DISCNUMBER,
    PARSED_TOTALDISCS,
    PARSED_TOTALTRACKS,
    PARSED_TRACKNUMBER,
)


def _tag_name_str(tag: ArbitraryTag) -> str:
    """Returns the str form of a tag name."""
    if isinstance(tag, Tag):
        return tag.name
    else:
        return tag


class Tags(frozendict.frozendict, Mapping[ArbitraryTag, Tuple[str, ...]]):
    """Tags, e.g., from a file/track or album.

    Note that tags can have multiple values, potentially even multiple identical
    values. E.g., this is a valid set of tags: {'a': ('b', 'b')}
    """

    def __init__(self, tags: Mapping[ArbitraryTag, Iterable[str]]) -> None:
        """Initializer.

        Args:
            tags: Tags to represent, as a mapping from each tag name to all
                values for that tag.
        """
        # TODO(https://github.com/python/typing/issues/256): Use a type
        # annotation instead of manually checking if the values are of type str.
        for name, values in tags.items():
            if isinstance(values, str):
                raise TypeError(
                    'Tags takes an iterable of values for each tag, found: '
                    f'{_tag_name_str(name)!r}={values!r}')
        super().__init__({
            _tag_name_str(name): tuple(values) for name, values in tags.items()
        })

    def __getitem__(self, key: ArbitraryTag) -> Tuple[str, ...]:
        return super().__getitem__(_tag_name_str(key))

    def __contains__(self, key: ArbitraryTag) -> bool:
        return super().__contains__(_tag_name_str(key))

    def derive(
            self,
            derived_tags: Iterable[DerivedTag] = _DERIVED_TAGS,
    ) -> 'Tags':
        """Returns a copy of self, with all specified derived tags set."""
        derived_tag_names = frozenset(tag.name for tag in derived_tags)
        tags = {
            name: values
            for name, values in self.items()
            if name not in derived_tag_names
        }
        for tag in derived_tags:
            values = tag.derive(self)
            if values:
                tags[tag] = values
        return Tags(tags)

    def one_or_none(self, key: ArbitraryTag) -> Optional[str]:
        """Returns a single value, or None if there isn't exactly one value."""
        values = self.get(key, ())
        if len(values) == 1:
            return values[0]
        else:
            return None

    def int_or_none(self, key: ArbitraryTag) -> Optional[int]:
        """Returns a single int value, or None if that's not possible."""
        value = self.one_or_none(key)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def singular(
            self,
            *keys: ArbitraryTag,
            default: str = '[unknown]',
            separator: str = '; ',
    ) -> str:
        """Returns a single value that represents all of a tag's values.

        Args:
            *keys: Which tags to look up. These are checked in order, and the
                first one that's present is used.
            default: What to return if there are no values.
            separator: What to put between values if there is more than one
                value.
        """
        for key in keys:
            if key in self:
                return separator.join(self[key])
        return default


def _compose_intersection(
        components_tags: Iterable[Tags]) -> Dict[str, Iterable[str]]:
    """Returns intersected tags."""
    if not components_tags:
        return {}

    tag_pair_counters = []
    for component_tags in components_tags:
        tag_pairs = []
        for name, values in component_tags.items():
            if name in (
                    DURATION_SECONDS.name,
                    DURATION_HUMAN.name,
            ):
                # These are not intersected.
                continue
            tag_pairs.extend((name, value) for value in values)
        tag_pair_counters.append(collections.Counter(tag_pairs))
    common_tag_pair_counter = functools.reduce(operator.and_, tag_pair_counters)

    tags = collections.defaultdict(list)
    for name, value in common_tag_pair_counter.elements():
        tags[name].append(value)
    return tags


def _compose_duration(
        components_tags: Iterable[Tags]) -> Dict[str, Iterable[str]]:
    """Returns summed duration tags."""
    duration_seconds_values = [
        component_tags.one_or_none(DURATION_SECONDS)
        for component_tags in components_tags
    ]
    if duration_seconds_values and None not in duration_seconds_values:
        try:
            return {
                DURATION_SECONDS.name:
                    (str(math.fsum(map(float, duration_seconds_values))),),
            }
        except ValueError:
            pass
    return {}


def compose(components_tags: Iterable[Tags]) -> Tags:
    """Returns the tags for an entity composed of tagged sub-entities.

    E.g., this can get the tags for an album composed of tracks. In general, the
    composite entity's tags are the intersection of its element's tags, but
    there are exceptions.

    Args:
        components_tags: Tags for all the components.
    """
    return Tags({
        **_compose_intersection(components_tags),
        **_compose_duration(components_tags),
    }).derive((DURATION_HUMAN,))
