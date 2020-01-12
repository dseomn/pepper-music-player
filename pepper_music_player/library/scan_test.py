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
"""Tests for pepper_music_player.library.scan."""

import io
import pathlib
import tempfile
import unittest

import mutagen.flac

from pepper_music_player.library import scan
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag

# Empty audio file data with no tags.
_FLAC = (
    b'fLaC\x80\x00\x00"\x10\x00\x10\x00\xff\xff\xff\x00\x00\x00\x0b\xb8\x00\xf0'
    b'\x00\x00\x00\x00\xd4\x1d\x8c\xd9\x8f\x00\xb2\x04\xe9\x80\t\x98\xec\xf8B~')


class ScanTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._root_dirpath = pathlib.Path(tempdir.name)

    def test_scans_recursively(self):
        self._root_dirpath.joinpath('empty-dir').mkdir()
        foo = self._root_dirpath.joinpath('foo')
        foo.mkdir()
        foo.joinpath('foo1').touch()
        foo.joinpath('foo2').touch()
        bar = foo.joinpath('bar')
        bar.mkdir()
        bar.joinpath('bar1').touch()
        self.assertCountEqual(
            (
                scan.File(dirname=str(foo), basename='foo1'),
                scan.File(dirname=str(foo), basename='foo2'),
                scan.File(dirname=str(bar), basename='bar1'),
            ),
            scan.scan(str(self._root_dirpath)),
        )

    def test_parses_empty_tags(self):
        self._root_dirpath.joinpath('foo.flac').write_bytes(_FLAC)
        self.assertCountEqual(
            (scan.AudioFile(
                dirname=str(self._root_dirpath),
                basename='foo.flac',
                track=entity.Track(tags=tag.Tags({
                    tag.BASENAME: ('foo.flac',),
                    tag.DIRNAME: (str(self._root_dirpath),),
                    tag.FILENAME:
                        (str(self._root_dirpath.joinpath('foo.flac')),),
                    tag.DURATION_SECONDS: ('0.0',),
                })),
            ),),
            scan.scan(str(self._root_dirpath)),
        )

    def test_parses_flac(self):
        flac_data = io.BytesIO(_FLAC)
        tags = mutagen.flac.FLAC(fileobj=flac_data)
        tags['title'] = 'Foo'
        tags['date'] = '2019-12-21'
        tags['artists'] = ['artist1', 'artist2']
        flac_data.seek(0)
        tags.save(flac_data)
        self._root_dirpath.joinpath('foo.flac').write_bytes(
            flac_data.getvalue())
        self.assertCountEqual(
            (scan.AudioFile(
                dirname=str(self._root_dirpath),
                basename='foo.flac',
                track=entity.Track(tags=tag.Tags({
                    'artists': ('artist1', 'artist2'),
                    'date': ('2019-12-21',),
                    'title': ('Foo',),
                    tag.BASENAME: ('foo.flac',),
                    tag.DIRNAME: (str(self._root_dirpath),),
                    tag.FILENAME:
                        (str(self._root_dirpath.joinpath('foo.flac')),),
                    tag.DURATION_SECONDS: ('0.0',),
                })),
            ),),
            scan.scan(str(self._root_dirpath)),
        )


if __name__ == '__main__':
    unittest.main()
