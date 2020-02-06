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
"""Helpers for the GTK main thread."""

import functools
import queue
from typing import Any, Callable

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib


def run_in_main_thread(function: Callable[..., None]) -> Callable[..., None]:
    """Decorator that makes a function run only in the main thread."""
    # This queue guarantees that the order of calls is preserved.
    calls = queue.SimpleQueue()

    def _main_thread_runner() -> None:
        args, kwargs = calls.get()
        function(*args, **kwargs)

    @functools.wraps(function)
    def _wrapper(*args: Any, **kwargs: Any) -> None:
        calls.put((args, kwargs))
        GLib.idle_add(_main_thread_runner)

    return _wrapper
