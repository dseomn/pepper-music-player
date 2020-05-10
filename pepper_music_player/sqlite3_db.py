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
"""Wrapper around sqlite3 for common management tasks."""

import contextlib
import dataclasses
import os
import sqlite3
import threading
import typing
from typing import Any, ContextManager, Generator, List, NewType, Optional, Sequence, Tuple, Type, TypeVar


@dataclasses.dataclass(frozen=True)
class SchemaItem:
    """Something in the schema, e.g., a table or index.

    Attributes:
        create: DDL statement to create the item.
    """
    create: str


@dataclasses.dataclass(frozen=True)
class Schema:
    """An entire schema.

    Attributes:
        name: Name of the schema, e.g., 'library' for things in the music
            library.
        version: Version of the schema, e.g., 'v1'.
        items: Things in the schema, e.g., tables and indexes.
    """
    name: str
    version: str
    items: Sequence[SchemaItem]


# Any type of transaction that supports reading.
AbstractSnapshot = NewType('AbstractSnapshot', sqlite3.Connection)

# Transaction for reading only.
Snapshot = NewType('Snapshot', AbstractSnapshot)

# Read-write transaction.
Transaction = NewType('Transaction', AbstractSnapshot)

# Any type of transaction.
AnyTransaction = TypeVar('AnyTransaction', Snapshot, Transaction)


class Database:
    """Wrapper around a sqlite3 database.

    This tries to minimize the amount of magic involved in sqlite3 (e.g., by
    making transaction management explicit) and choose reasonable defaults.
    """

    # TODO(dseomn): Add support for database schema version migration.

    def __init__(
            self,
            schema: Schema,
            *,
            database_dir: str,
            reverse_unordered_selects: bool = False,
    ) -> None:
        """Initializer.

        Args:
            schema: Schema for the database.
            database_dir: Directory containing databases.
            reverse_unordered_selects: See
                https://www.sqlite.org/pragma.html#pragma_reverse_unordered_selects.
                This is probably only useful for tests to make sure they're not
                relying on undefined ordering of SQL queries.
        """
        # TODO(dseomn): Change database_dir to Optional[str], where None
        # indicates to use the default directory.
        self._filename = os.path.join(
            database_dir, f'{schema.name}.{schema.version}.sqlite3')
        self._schema = schema
        self._reverse_unordered_selects = reverse_unordered_selects
        self._local = threading.local()

        if not os.path.exists(self._filename):
            with self.transaction() as transaction:
                for item in self._schema.items:
                    transaction.execute(item.create)

    @property
    def _connection(self) -> sqlite3.Connection:
        """Connection to the database."""
        # https://docs.python.org/3.8/library/sqlite3.html#multithreading says
        # that sqlite3 connections shouldn't be shared between threads.
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self._filename,
                                                     isolation_level=None)
            self._local.connection.execute('PRAGMA journal_mode=WAL')
            self._local.connection.execute('PRAGMA foreign_keys=ON')
            if self._reverse_unordered_selects:
                self._local.connection.execute(
                    'PRAGMA reverse_unordered_selects=ON')
        return self._local.connection

    @contextlib.contextmanager
    def _transaction(
            self,
            mode: str,
            transaction_type: Type[AnyTransaction],
    ) -> Generator[AnyTransaction, None, None]:  # yapf: disable
        """Returns a context manager around a transaction.

        This behaves like the connection context manager is supposed to, but
        works with isolation_level=None. See
        https://docs.python.org/3/library/sqlite3.html#using-the-connection-as-a-context-manager
        and https://bugs.python.org/issue16958 for more details. Additionally,
        this context manager returns the connection itself, so that the only way
        to use the connection is while it's in an explicit transaction.

        Args:
            mode: Which type of transaction to use, see
                https://www.sqlite.org/lang_transaction.html
            transaction_type: Which type of transaction to return. (This should
                match mode.)
        """
        # TODO(https://github.com/google/yapf/issues/793): Remove the yapf
        # disable comment above.
        self._connection.execute(f'BEGIN {mode} TRANSACTION')
        try:
            yield transaction_type(self._connection)
        except:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()

    @typing.overload
    def snapshot(self, snapshot: None = None) -> ContextManager[Snapshot]:
        pass

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    @typing.overload
    def snapshot(
            self,
            snapshot: AbstractSnapshot,
    ) -> ContextManager[AbstractSnapshot]:  # yapf: disable
        pass

    def snapshot(self, snapshot=None):
        """Returns a context manager around a snapshot (read-only transaction).

        Unfortunately, sqlite3 does not seem to provide true read-only
        transactions, so this uses DEFERRED instead. Still, prefer transaction()
        below if you want a read-write transaction. Hopefully the name of this
        function will make it clear when snapshots are being accidentally used
        for writing.

        Args:
            snapshot: An existing snapshot to reuse instead of starting another
                one.
        """
        if snapshot is None:
            return self._transaction('DEFERRED', Snapshot)
        else:
            return contextlib.nullcontext(snapshot)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def transaction(
            self,
            transaction: Optional[Transaction] = None,
    ) -> ContextManager[Transaction]:  # yapf: disable
        """Returns a context manager around a read-write transaction.

        Args:
            transaction: An existing transaction to reuse instead of starting
                another one.
        """
        if transaction is None:
            return self._transaction('EXCLUSIVE', Transaction)
        else:
            return contextlib.nullcontext(transaction)


class QueryBuilder:
    """Builder for SQL queries."""

    def __init__(self) -> None:
        self._sql: List[str] = []
        self._parameters: List[Any] = []

    def append(self, sql: str, parameters: Sequence[Any] = ()) -> None:
        """Appends to the query being built.

        Args:
            sql: SQL to append to the query.
            parameters: Parameters for sql.
        """
        self._sql.append(sql)
        self._parameters.extend(parameters)

    def build(self) -> Tuple[str, Sequence[Any]]:
        """Returns the built query and its parameters.

        Typical usage:
            outer_builder.append(*inner_builder.build())

            transaction.execute(*builder.build())
        """
        return ' '.join(self._sql), tuple(self._parameters)
