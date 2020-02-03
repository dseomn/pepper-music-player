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
"""Formatting utils for metadata."""

import datetime
from typing import TypeVar, Union

T = TypeVar('T')


def format_timedelta(
        timedelta: datetime.timedelta,
        *,
        default: T = '‒∶‒‒',
) -> Union[str, T]:
    """Returns a non-negative timedelta formatted for human consumption.

    Args:
        timedelta: What to format.
        default: What to return if timedelta is negative.
    """
    total_seconds = round(timedelta.total_seconds())
    if total_seconds < 0:
        return default
    hours, hours_remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(hours_remainder, 60)
    if hours:
        return f'{hours}∶{minutes:02}∶{seconds:02}'
    else:
        return f'{minutes}∶{seconds:02}'
