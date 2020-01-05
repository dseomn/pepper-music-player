# Copyright 2019 Google LLC
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
"""Tests for pepper_music_player.metadata."""

import unittest

from pepper_music_player import metadata


class TagsTest(unittest.TestCase):

    def test_init_converts_values_to_tuple(self):
        self.assertEqual(
            ('a', 'b'),
            metadata.Tags({'foo': ['a', 'b']})['foo'],
        )

    def test_getitem_str(self):
        self.assertEqual(('b',), metadata.Tags({'a': ('b',)})['a'])

    def test_getitem_tag_name(self):
        self.assertEqual(
            ('a',),
            metadata.Tags({'album': ('a',)})[metadata.TagName.ALBUM],
        )

    def test_contains_str(self):
        self.assertIn('a', metadata.Tags({'a': ('b',)}))

    def test_contains_tag_name(self):
        self.assertIn(metadata.TagName.ALBUM, metadata.Tags({'album': ('a',)}))

    def test_one_or_none_with_zero(self):
        self.assertIs(None, metadata.Tags({}).one_or_none('a'))

    def test_one_or_none_with_one(self):
        self.assertEqual('foo', metadata.Tags({'a': ('foo',)}).one_or_none('a'))

    def test_one_or_none_with_multiple(self):
        self.assertIs(
            None,
            metadata.Tags({
                'a': ('foo', 'bar'),
            }).one_or_none('a'),
        )

    def test_singular_with_zero(self):
        self.assertEqual('[unknown]',
                         metadata.Tags({}).singular('a', default='[unknown]'))

    def test_singular_with_one(self):
        self.assertEqual('foo', metadata.Tags({'a': ('foo',)}).singular('a'))

    def test_singular_with_multiple(self):
        self.assertEqual(
            'foo; bar',
            metadata.Tags({
                'a': ('foo', 'bar'),
            }).singular('a', separator='; '),
        )

    def test_tracknumber_none(self):
        self.assertIs(None, metadata.Tags({}).tracknumber)

    def test_tracknumber_unknown_format(self):
        self.assertEqual('foo',
                         metadata.Tags(dict(tracknumber=('foo',))).tracknumber)

    def test_tracknumber_simple(self):
        self.assertEqual('1',
                         metadata.Tags(dict(tracknumber=('1',))).tracknumber)

    def test_tracknumber_with_totaltracks(self):
        self.assertEqual('1',
                         metadata.Tags(dict(tracknumber=('1/21',))).tracknumber)


class TokenTest(unittest.TestCase):

    def test_token_str(self):
        self.assertEqual('foo', str(metadata.Token('foo')))


class AudioFileTest(unittest.TestCase):

    def test_token_different(self):
        self.assertNotEqual(
            metadata.AudioFile(
                dirname='/a',
                filename='b',
                tags=metadata.Tags({}),
            ).token,
            metadata.AudioFile(
                dirname='/a',
                filename='c',
                tags=metadata.Tags({}),
            ).token,
        )

    def test_album_token_same(self):
        self.assertEqual(
            metadata.AudioFile(
                dirname='/a',
                filename='b',
                tags=metadata.Tags({'album': ('a',)}),
            ).album_token,
            metadata.AudioFile(
                dirname='/a',
                filename='c',
                tags=metadata.Tags({'album': ('a',)}),
            ).album_token,
        )

    def test_album_token_different(self):
        self.assertNotEqual(
            metadata.AudioFile(
                dirname='/a',
                filename='b',
                tags=metadata.Tags({'album': ('a',)}),
            ).album_token,
            metadata.AudioFile(
                dirname='/a',
                filename='c',
                tags=metadata.Tags({'album': ('d',)}),
            ).album_token,
        )


class AlbumTest(unittest.TestCase):

    def test_token(self):
        tracks = (
            metadata.AudioFile(
                dirname='/a',
                filename='b',
                tags=metadata.Tags({'album': ('a',)}),
            ),
            metadata.AudioFile(
                dirname='/a',
                filename='c',
                tags=metadata.Tags({'album': ('a',)}),
            ),
        )
        self.assertEqual(
            tracks[0].album_token,
            metadata.Album(tags=metadata.Tags({}), tracks=tracks).token,
        )

    def test_token_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'exactly one token'):
            metadata.Album(
                tags=metadata.Tags({}),
                tracks=(
                    metadata.AudioFile(
                        dirname='/a',
                        filename='b',
                        tags=metadata.Tags({'album': ('a',)}),
                    ),
                    metadata.AudioFile(
                        dirname='/a',
                        filename='c',
                        tags=metadata.Tags({'album': ('d',)}),
                    ),
                ),
            )


if __name__ == '__main__':
    unittest.main()
