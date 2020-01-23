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
"""Publish-subscribe system."""

from concurrent import futures
import dataclasses
import threading
from typing import Callable, Generic, List, Type, TypeVar


@dataclasses.dataclass(frozen=True)
class Message:
    """Base class for messages sent over pubsub.

    All messages must be immutable, since they are shared across threads and
    across subscribers.
    """


AnyMessage = TypeVar('AnyMessage', bound=Message)


@dataclasses.dataclass(frozen=True)
class _Subscriber(Generic[AnyMessage]):
    # TODO(dseomn): Remove these pytype disables.
    message_type: Type[AnyMessage]  # pytype: disable=not-supported-yet
    callback: Callable[[AnyMessage], None]  # pytype: disable=not-supported-yet


class PubSub:
    """In-memory publish-subscribe message bus."""

    def __init__(self) -> None:
        self._subscribers: List[_Subscriber] = []
        self._subscribers_lock = threading.Lock()
        self._pool = futures.ThreadPoolExecutor()

    def shutdown(self) -> None:
        """Shuts down the message bus.

        After this method starts, calls to other methods are not supported and
        may raise exceptions.
        """
        self._pool.shutdown()

    def _send(self, message: Message) -> None:
        """Sends a message to all appropriate subscribers."""
        with self._subscribers_lock:
            for subscriber in self._subscribers:
                if isinstance(message, subscriber.message_type):
                    self._pool.submit(subscriber.callback, message)

    def publish(self, message: Message) -> None:
        """Publishes a message."""
        self._pool.submit(self._send, message)

    def subscribe(
            self,
            message_type: Type[AnyMessage],
            callback: Callable[[AnyMessage], None],
    ) -> None:
        """Subscribes to a message type.

        Args:
            message_type: What type of message to subscribe to.
            callback: Function that is called for every published message of the
                appropriate type.
        """
        with self._subscribers_lock:
            self._subscribers.append(_Subscriber(message_type, callback))
