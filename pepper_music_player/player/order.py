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
"""Play orders."""

import enum
import functools
import logging
from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')


class StopError(Exception):
    """Exception to stop playback due to an error."""


class ErrorPolicy(enum.Enum):
    """What an Order should do when there's an error.

    Attributes:
        RETURN_NONE: Return None, as if it were a normal stop condition.
        RAISE_STOP_ERROR: Raise StopError.
        DEFAULT: Default policy if none is specified, RETURN_NONE.
    """
    RETURN_NONE = enum.auto()
    RAISE_STOP_ERROR = enum.auto()
    DEFAULT = RETURN_NONE


def handle_stop_error(function: Callable[..., T]) -> Callable[..., Optional[T]]:
    """Decorator to handle ErrorPolicy for a function.

    Args:
        function: A function with an 'error_policy' keyword argument, that
            raises StopError on error.

    Returns:
        A function that respects the error_policy argument.
    """

    @functools.wraps(function)
    def _wrapper(
            *args: Any,
            error_policy: ErrorPolicy = ErrorPolicy.DEFAULT,
            **kwargs: Any,
    ) -> Optional[T]:
        try:
            return function(*args,
                            error_policy=ErrorPolicy.RAISE_STOP_ERROR,
                            **kwargs)
        except StopError:
            if error_policy is ErrorPolicy.RAISE_STOP_ERROR:
                raise
            else:
                assert error_policy is ErrorPolicy.RETURN_NONE
                logging.exception('Stopping due to error.')
                return None

    return _wrapper
