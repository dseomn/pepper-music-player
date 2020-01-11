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
"""Tests for pepper_music_player.metadata.entity."""

import unittest

from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag


class AudioFileTest(unittest.TestCase):

    def test_token_different(self):
        self.assertNotEqual(
            entity.AudioFile(
                dirname='/a',
                filename='b',
                tags=tag.Tags({}),
            ).token,
            entity.AudioFile(
                dirname='/a',
                filename='c',
                tags=tag.Tags({}),
            ).token,
        )

    def test_album_token_same(self):
        self.assertEqual(
            entity.AudioFile(
                dirname='/a',
                filename='b',
                tags=tag.Tags({'album': ('a',)}),
            ).album_token,
            entity.AudioFile(
                dirname='/a',
                filename='c',
                tags=tag.Tags({'album': ('a',)}),
            ).album_token,
        )

    def test_album_token_different(self):
        self.assertNotEqual(
            entity.AudioFile(
                dirname='/a',
                filename='b',
                tags=tag.Tags({'album': ('a',)}),
            ).album_token,
            entity.AudioFile(
                dirname='/a',
                filename='c',
                tags=tag.Tags({'album': ('d',)}),
            ).album_token,
        )


class AlbumTest(unittest.TestCase):

    def test_token(self):
        tracks = (
            entity.AudioFile(
                dirname='/a',
                filename='b',
                tags=tag.Tags({'album': ('a',)}),
            ),
            entity.AudioFile(
                dirname='/a',
                filename='c',
                tags=tag.Tags({'album': ('a',)}),
            ),
        )
        self.assertEqual(
            tracks[0].album_token,
            entity.Album(tags=tag.Tags({}), tracks=tracks).token,
        )

    def test_token_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'exactly one token'):
            entity.Album(
                tags=tag.Tags({}),
                tracks=(
                    entity.AudioFile(
                        dirname='/a',
                        filename='b',
                        tags=tag.Tags({'album': ('a',)}),
                    ),
                    entity.AudioFile(
                        dirname='/a',
                        filename='c',
                        tags=tag.Tags({'album': ('d',)}),
                    ),
                ),
            )


if __name__ == '__main__':
    unittest.main()