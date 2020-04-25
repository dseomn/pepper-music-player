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

import dataclasses
import logging
import queue
import threading
from typing import Callable, Dict, Generic, List, NoReturn, Type, TypeVar


@dataclasses.dataclass(frozen=True)
class Message:
    """Base class for messages sent over pubsub.

    All messages must be immutable, since they are shared across threads and
    across subscribers.
    """


AnyMessage = TypeVar('AnyMessage', bound=Message)


@dataclasses.dataclass(frozen=True)
class _Subscriber(Generic[AnyMessage]):
    # TODO(dseomn): Remove pytype disable.
    message_type: Type[AnyMessage]  # pytype: disable=not-supported-yet
    queue: 'queue.Queue[AnyMessage]' = dataclasses.field(
        default_factory=queue.Queue)  # pytype: disable=not-supported-yet


class PubSub:
    """In-memory publish-subscribe message bus.

    Each subscriber (identified by a call to the subscribe method) is guaranteed
    to receive messages in the order they were published. No guarantees are made
    about the order of message between subscribers.

    Message types are matched exactly. I.e., a subscriber to a parent class will
    not receive messages of a subclass type. While this is somewhat
    non-pythonic, it should make it easier to port this to a real, distributed
    pubsub system if/when needed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: List[_Subscriber] = []
        self._last_message_by_type: Dict[Type[AnyMessage], AnyMessage] = {}

    def join(self) -> None:
        """Waits for all messages to be processed.

        This is an expensive method that holds the lock potentially much longer
        than other methods. It's primarily intended for testing, and for before
        the application exits.
        """
        # TODO(dseomn): This could deadlock if one of the subscriber callbacks
        # tries to publish (or subscribe). Does that matter?
        with self._lock:
            for subscriber in self._subscribers:
                subscriber.queue.join()

    def publish(self, message: Message) -> None:
        """Publishes a message."""
        with self._lock:
            self._last_message_by_type[type(message)] = message
            for subscriber in self._subscribers:
                if type(message) == subscriber.message_type:  # pylint: disable=unidiomatic-typecheck
                    subscriber.queue.put(message)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _process_subscriber_queue(
            self,
            subscriber_queue: 'queue.Queue[AnyMessage]',
            callback: Callable[[AnyMessage], None],
    ) -> NoReturn:  # yapf: disable
        """Processes messages for a single subscriber, in a daemon thread."""
        while True:
            message = subscriber_queue.get()
            try:
                callback(message)
            except Exception:  # pylint: disable=broad-except
                logging.exception('Subscriber %r failed to process message %r',
                                  callback, message)
            finally:
                subscriber_queue.task_done()

    def subscribe(
            self,
            message_type: Type[AnyMessage],
            callback: Callable[[AnyMessage], None],
            *,
            want_last_message: bool = False,
    ) -> None:
        """Subscribes to a message type.

        Args:
            message_type: What type of message to subscribe to.
            callback: Function that is called for every published message of the
                appropriate type.
            want_last_message: If True and any messages of the appropriate type
                have been previously published, callback will be called with the
                last of those messages, before receiving new messages.
        """
        subscriber = _Subscriber(message_type)
        threading.Thread(
            target=self._process_subscriber_queue,
            args=(subscriber.queue, callback),
            daemon=True,
        ).start()
        with self._lock:
            if want_last_message and message_type in self._last_message_by_type:
                subscriber.queue.put(self._last_message_by_type[message_type])
            self._subscribers.append(subscriber)
