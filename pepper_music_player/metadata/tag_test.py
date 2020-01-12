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
"""Tests for pepper_music_player.metadata.tag."""

import unittest

from pepper_music_player.metadata import tag


class PseudoTagTest(unittest.TestCase):

    def test_requires_prefix(self):
        with self.assertRaisesRegex(ValueError, "must start with '~'"):
            tag.PseudoTag('foo')


class DurationHumanTagTest(unittest.TestCase):

    def test_none(self):
        self.assertIs(None, tag.DURATION_HUMAN.derive(tag.Tags({})))

    def test_invalid(self):
        self.assertIs(
            None,
            tag.DURATION_HUMAN.derive(tag.Tags({
                '~duration_seconds': ('foo',),
            })),
        )

    def test_negative(self):
        self.assertIs(
            None,
            tag.DURATION_HUMAN.derive(tag.Tags({
                '~duration_seconds': ('-1',),
            })),
        )

    def test_hours_minutes_seconds(self):
        self.assertEqual(
            ('1∶02∶03',),
            tag.DURATION_HUMAN.derive(
                tag.Tags({'~duration_seconds': ('3723.4',)})),
        )

    def test_minutes_seconds(self):
        self.assertEqual(
            ('1∶02',),
            tag.DURATION_HUMAN.derive(
                tag.Tags({
                    '~duration_seconds': ('62.3',),
                })),
        )

    def test_seconds(self):
        self.assertEqual(
            ('0∶01',),
            tag.DURATION_HUMAN.derive(tag.Tags({
                '~duration_seconds': ('1.2',),
            })),
        )


class IndexOrTotalTagTest(unittest.TestCase):

    def test_none(self):
        tags = tag.Tags({})
        self.assertIs(None, tag.PARSED_TRACKNUMBER.derive(tags))
        self.assertIs(None, tag.PARSED_TOTALTRACKS.derive(tags))
        self.assertIs(None, tag.PARSED_DISCNUMBER.derive(tags))
        self.assertIs(None, tag.PARSED_TOTALDISCS.derive(tags))

    def test_plain(self):
        tags = tag.Tags({
            'tracknumber': ('1',),
            'totaltracks': ('10',),
            'discnumber': ('2',),
            'totaldiscs': ('20',),
        })
        self.assertEqual(('1',), tag.PARSED_TRACKNUMBER.derive(tags))
        self.assertEqual(('10',), tag.PARSED_TOTALTRACKS.derive(tags))
        self.assertEqual(('2',), tag.PARSED_DISCNUMBER.derive(tags))
        self.assertEqual(('20',), tag.PARSED_TOTALDISCS.derive(tags))

    def test_composite_unknown_format(self):
        tags = tag.Tags({
            'tracknumber': ('trackN',),
            'discnumber': ('discN',),
        })
        self.assertEqual(('trackN',), tag.PARSED_TRACKNUMBER.derive(tags))
        self.assertIs(None, tag.PARSED_TOTALTRACKS.derive(tags))
        self.assertEqual(('discN',), tag.PARSED_DISCNUMBER.derive(tags))
        self.assertIs(None, tag.PARSED_TOTALDISCS.derive(tags))

    def test_composite_index_only(self):
        tags = tag.Tags({
            'tracknumber': ('1',),
            'discnumber': ('2',),
        })
        self.assertEqual(('1',), tag.PARSED_TRACKNUMBER.derive(tags))
        self.assertIs(None, tag.PARSED_TOTALTRACKS.derive(tags))
        self.assertEqual(('2',), tag.PARSED_DISCNUMBER.derive(tags))
        self.assertIs(None, tag.PARSED_TOTALDISCS.derive(tags))

    def test_composite_complete(self):
        tags = tag.Tags({
            'tracknumber': ('1/10',),
            'discnumber': ('2/20',),
        })
        self.assertEqual(('1',), tag.PARSED_TRACKNUMBER.derive(tags))
        self.assertEqual(('10',), tag.PARSED_TOTALTRACKS.derive(tags))
        self.assertEqual(('2',), tag.PARSED_DISCNUMBER.derive(tags))
        self.assertEqual(('20',), tag.PARSED_TOTALDISCS.derive(tags))


class TagsTest(unittest.TestCase):

    def test_init_converts_names_to_str(self):
        self.assertEqual(
            ('foo',),
            tag.Tags({tag.BASENAME: ('foo',)})['~basename'],
        )

    def test_init_converts_values_to_tuple(self):
        self.assertEqual(
            ('a', 'b'),
            tag.Tags({'foo': ['a', 'b']})['foo'],
        )

    def test_getitem_str(self):
        self.assertEqual(('b',), tag.Tags({'a': ('b',)})['a'])

    def test_getitem_tag_name(self):
        self.assertEqual(
            ('a',),
            tag.Tags({'album': ('a',)})[tag.ALBUM],
        )

    def test_contains_str(self):
        self.assertIn('a', tag.Tags({'a': ('b',)}))

    def test_contains_tag_name(self):
        self.assertIn(tag.ALBUM, tag.Tags({'album': ('a',)}))

    def test_derive_removes_old_derived_values(self):
        self.assertEqual(
            tag.Tags({
                '~basename': ('foo',),
            }),
            tag.Tags({
                '~basename': ('foo',),
                '~parsed_discnumber': ('1',),
            }).derive(),
        )

    def test_derive_adds_new_derived_values(self):
        self.assertEqual(
            tag.Tags({
                'tracknumber': ('1/10',),
                'discnumber': ('2/20',),
                '~parsed_tracknumber': ('1',),
                '~parsed_totaltracks': ('10',),
                '~parsed_discnumber': ('2',),
                '~parsed_totaldiscs': ('20',),
                '~duration_seconds': ('1',),
                '~duration_human': ('0∶01',),
            }),
            tag.Tags({
                'tracknumber': ('1/10',),
                'discnumber': ('2/20',),
                '~duration_seconds': ('1',),
            }).derive(),
        )

    def test_one_or_none_with_zero(self):
        self.assertIs(None, tag.Tags({}).one_or_none('a'))

    def test_one_or_none_with_one(self):
        self.assertEqual('foo', tag.Tags({'a': ('foo',)}).one_or_none('a'))

    def test_one_or_none_with_multiple(self):
        self.assertIs(
            None,
            tag.Tags({
                'a': ('foo', 'bar'),
            }).one_or_none('a'),
        )

    def test_singular_with_zero(self):
        self.assertEqual('[unknown]',
                         tag.Tags({}).singular('a', default='[unknown]'))

    def test_singular_with_one(self):
        self.assertEqual('foo', tag.Tags({'a': ('foo',)}).singular('a'))

    def test_singular_with_multiple(self):
        self.assertEqual(
            'foo; bar',
            tag.Tags({
                'a': ('foo', 'bar'),
            }).singular('a', separator='; '),
        )

    def test_compose_empty(self):
        self.assertEqual(tag.Tags({}), tag.compose(()))

    def test_compose_identity(self):
        tags = tag.Tags({
            'foo': ('foo1', 'foo2'),
            'bar': ('bar',),
        })
        self.assertEqual(tags, tag.compose((tags,)))

    def test_compose_intersection(self):
        self.assertEqual(
            tag.Tags({
                'common': ('foo', 'foo'),
                'partially_common': ('common',),
                '~parsed_totaltracks': ('2',),
            }),
            tag.compose((
                tag.Tags({
                    'common': ('foo', 'foo'),
                    'partially_common': ('common', 'diff1'),
                    'different': ('diff1',),
                    'tracknumber': ('1/2',),
                    '~parsed_tracknumber': ('1',),
                    '~parsed_totaltracks': ('2',),
                }),
                tag.Tags({
                    'common': ('foo', 'foo'),
                    'partially_common': ('common', 'common', 'diff2'),
                    'different': ('diff2',),
                    'tracknumber': ('2/2',),
                    '~parsed_tracknumber': ('2',),
                    '~parsed_totaltracks': ('2',),
                }),
            )),
        )


if __name__ == '__main__':
    unittest.main()
