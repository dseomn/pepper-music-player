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
from pepper_music_player.metadata import token


class LibraryEntityTest(unittest.TestCase):

    def test_track_token_format(self):
        self.assertEqual(
            "track/v1alpha:(('~filename', '/a/b'),)",
            str(entity.Track(tags=tag.Tags({tag.FILENAME: ('/a/b',)})).token),
        )

    def test_medium_token_format_minimal(self):
        self.assertEqual(
            "medium/v1alpha:(('~dirname', '/a'),)",
            str(
                entity.Track(
                    tags=tag.Tags({tag.DIRNAME: ('/a',)})).medium_token),
        )

    def test_medium_token_format_full(self):
        self.assertEqual(
            'medium/v1alpha:('
            "('~dirname', '/a'), "
            "('album', 'an album'), "
            "('albumartist', 'an album artist'), "
            "('musicbrainz_albumid', 'ef83d7bf-10c3-448b-810d-16c3d1f0ce88'), "
            "('~parsed_discnumber', '1'))",
            str(
                entity.Track(tags=tag.Tags({
                    tag.DIRNAME: ('/a',),
                    tag.ALBUM: ('an album',),
                    tag.ALBUMARTIST: ('an album artist',),
                    tag.MUSICBRAINZ_ALBUMID: (
                        'ef83d7bf-10c3-448b-810d-16c3d1f0ce88',),
                    tag.DISCNUMBER: ('1',),
                }).derive()).medium_token),
        )

    def test_album_token_format_minimal(self):
        self.assertEqual(
            "album/v1alpha:(('~dirname', '/a'),)",
            str(
                entity.Track(
                    tags=tag.Tags({tag.DIRNAME: ('/a',)})).album_token),
        )

    def test_album_token_format_full(self):
        self.assertEqual(
            'album/v1alpha:('
            "('~dirname', '/a'), "
            "('album', 'an album'), "
            "('albumartist', 'an album artist'), "
            "('musicbrainz_albumid', 'ef83d7bf-10c3-448b-810d-16c3d1f0ce88'))",
            str(
                entity.Track(tags=tag.Tags({
                    tag.DIRNAME: ('/a',),
                    tag.ALBUM: ('an album',),
                    tag.ALBUMARTIST: ('an album artist',),
                    tag.MUSICBRAINZ_ALBUMID: (
                        'ef83d7bf-10c3-448b-810d-16c3d1f0ce88',),
                    tag.DISCNUMBER: ('1',),
                }).derive()).album_token),
        )

    def test_track_token_different(self):
        self.assertNotEqual(
            entity.Track(tags=tag.Tags({tag.FILENAME: ('/a/b',)})).token,
            entity.Track(tags=tag.Tags({tag.FILENAME: ('/a/c',)})).token,
        )

    def test_album_and_medium_token_same(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('b',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/b',),
            tag.ALBUM: ('a',),
            tag.DISCNUMBER: ('1',),
        }).derive())
        track2 = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('c',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/c',),
            tag.ALBUM: ('a',),
            tag.DISCNUMBER: ('1',),
        }).derive())
        medium = entity.Medium(tags=tag.Tags({}), tracks=(track1, track2))
        album = entity.Album(tags=tag.Tags({}), mediums=(medium,))
        self.assertEqual(
            1,
            len({track1.medium_token, track2.medium_token, medium.token}),
        )
        self.assertEqual(
            1,
            len({
                track1.album_token,
                track2.album_token,
                medium.album_token,
                album.token,
            }),
        )

    def test_album_but_not_medium_token_same(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('b',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/b',),
            tag.ALBUM: ('a',),
            tag.DISCNUMBER: ('1',),
        }).derive())
        medium1 = entity.Medium(tags=tag.Tags({}), tracks=(track1,))
        track2 = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('c',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/c',),
            tag.ALBUM: ('a',),
            tag.DISCNUMBER: ('2',),
        }).derive())
        medium2 = entity.Medium(tags=tag.Tags({}), tracks=(track2,))
        album = entity.Album(tags=tag.Tags({}), mediums=(medium1, medium2))
        self.assertNotEqual(track1.medium_token, track2.medium_token)
        self.assertEqual(track1.medium_token, medium1.token)
        self.assertEqual(track2.medium_token, medium2.token)
        self.assertEqual(
            1,
            len({
                track1.album_token,
                track2.album_token,
                medium1.album_token,
                medium2.album_token,
                album.token,
            }),
        )

    def test_album_and_medium_token_different(self):
        track1 = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('b',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/b',),
            tag.ALBUM: ('a',),
            tag.DISCNUMBER: ('1',),
        }).derive())
        medium1 = entity.Medium(tags=tag.Tags({}), tracks=(track1,))
        track2 = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('c',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/c',),
            tag.ALBUM: ('d',),
            tag.DISCNUMBER: ('1',),
        }).derive())
        medium2 = entity.Medium(tags=tag.Tags({}), tracks=(track2,))
        self.assertNotEqual(track1.medium_token, track2.medium_token)
        self.assertNotEqual(track1.album_token, track2.album_token)
        with self.assertRaisesRegex(ValueError, 'exactly one token'):
            entity.Medium(tags=tag.Tags({}), tracks=(track1, track2))
        with self.assertRaisesRegex(ValueError, 'exactly one token'):
            entity.Album(tags=tag.Tags({}), mediums=(medium1, medium2))

    def test_track_sort_key(self):
        track = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('b',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/b',),
            tag.DISCNUMBER: ('1',),
            tag.TRACKNUMBER: ('2',),
        }).derive())
        self.assertEqual(
            b''.join((
                b'\x00',
                b'\x00' * 7 + b'\x01',
                b'\x00' * 7 + b'\x02',
            )),
            track.sort_key,
        )

    def test_track_sort_key_default(self):
        track = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('b',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/b',),
        }).derive())
        self.assertEqual(
            b''.join((
                b'\x00',
                b'\x00' * 8,
                b'\x00' * 8,
            )),
            track.sort_key,
        )

    def test_medium_sort_key(self):
        track = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('b',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/b',),
            tag.DISCNUMBER: ('1',),
        }).derive())
        self.assertEqual(
            b''.join((
                b'\x00',
                b'\x00' * 7 + b'\x01',
            )),
            track.medium_sort_key,
        )

    def test_medium_sort_key_default(self):
        track = entity.Track(tags=tag.Tags({
            tag.BASENAME: ('b',),
            tag.DIRNAME: ('/a',),
            tag.FILENAME: ('/a/b',),
        }).derive())
        self.assertEqual(
            b''.join((
                b'\x00',
                b'\x00' * 8,
            )),
            track.medium_sort_key,
        )


class PlaylistEntryTest(unittest.TestCase):

    def test_token_format(self):
        self.assertRegex(
            str(
                entity.PlaylistEntry(
                    library_token=token.Track('irrelevant-token')).token),
            r'^playlistEntry/v1alpha:'
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        )

    def test_tokens_are_unique(self):
        library_token = token.Track('irrelevant-token')
        self.assertNotEqual(
            entity.PlaylistEntry(library_token=library_token).token,
            entity.PlaylistEntry(library_token=library_token).token)

    def test_token_can_be_specified(self):
        library_token = token.Track('irrelevant-token')
        entry = entity.PlaylistEntry(library_token=library_token)
        self.assertEqual(
            entry.token,
            entity.PlaylistEntry(
                token=entry.token,
                library_token=library_token,
            ).token,
        )


if __name__ == '__main__':
    unittest.main()
