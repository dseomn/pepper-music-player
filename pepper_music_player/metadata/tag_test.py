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


class TagsTest(unittest.TestCase):

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
            tag.Tags({'album': ('a',)})[tag.TagName.ALBUM],
        )

    def test_contains_str(self):
        self.assertIn('a', tag.Tags({'a': ('b',)}))

    def test_contains_tag_name(self):
        self.assertIn(tag.TagName.ALBUM, tag.Tags({'album': ('a',)}))

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

    def test_tracknumber_none(self):
        self.assertIs(None, tag.Tags({}).tracknumber)

    def test_tracknumber_unknown_format(self):
        self.assertEqual('foo',
                         tag.Tags(dict(tracknumber=('foo',))).tracknumber)

    def test_tracknumber_simple(self):
        self.assertEqual('1', tag.Tags(dict(tracknumber=('1',))).tracknumber)

    def test_tracknumber_with_totaltracks(self):
        self.assertEqual('1', tag.Tags(dict(tracknumber=('1/21',))).tracknumber)

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
            }),
            tag.compose((
                tag.Tags({
                    'common': ('foo', 'foo'),
                    'partially_common': ('common', 'diff1'),
                    'different': ('diff1',),
                }),
                tag.Tags({
                    'common': ('foo', 'foo'),
                    'partially_common': ('common', 'common', 'diff2'),
                    'different': ('diff2',),
                }),
            )),
        )


if __name__ == '__main__':
    unittest.main()
