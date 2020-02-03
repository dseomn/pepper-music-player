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
"""Tests for pepper_music_player.metadata.formatting."""

import datetime
import unittest

from pepper_music_player.metadata import formatting


class FormatTimedeltaTest(unittest.TestCase):

    def test_none(self):
        self.assertEqual('‒∶‒‒', formatting.format_timedelta(None))

    def test_negative(self):
        self.assertEqual('‒∶‒‒',
                         formatting.format_timedelta(datetime.timedelta(-1)))

    def test_hours_minutes_seconds(self):
        self.assertEqual(
            '1∶02∶03',
            formatting.format_timedelta(
                datetime.timedelta(hours=1, minutes=2, seconds=3)))

    def test_minutes_seconds(self):
        self.assertEqual(
            '1∶02',
            formatting.format_timedelta(datetime.timedelta(minutes=1,
                                                           seconds=2)))

    def test_seconds(self):
        self.assertEqual(
            '0∶01', formatting.format_timedelta(datetime.timedelta(seconds=1)))


if __name__ == '__main__':
    unittest.main()
