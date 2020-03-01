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
"""Tests for pepper_music_player.sqlite3_db."""

import tempfile
import unittest

from pepper_music_player import sqlite3_db

_SCHEMA = sqlite3_db.Schema(
    name='test',
    version='v1alpha',
    items=(
        sqlite3_db.SchemaItem("""
            CREATE TABLE Test (
                foo TEXT,
                bar TEXT,
                PRIMARY KEY (foo)
            )
        """),
        sqlite3_db.SchemaItem('CREATE INDEX Test_BarIndex ON Test (bar)'),
        sqlite3_db.SchemaItem("""
            CREATE TABLE DependsOnTest (
                foo TEXT REFERENCES Test (foo) ON DELETE CASCADE
            )
        """),
    ),
)


class DatabaseTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._db = sqlite3_db.Database(_SCHEMA, database_dir=tempdir.name)
        self._db_reverse_unordered_select = sqlite3_db.Database(
            _SCHEMA, database_dir=tempdir.name, reverse_unordered_selects=True)

    def test_schema_created_only_on_initial_open(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        with sqlite3_db.Database(
                _SCHEMA,
                database_dir=tempdir.name).transaction() as transaction:
            transaction.execute(
                "INSERT INTO Test (foo, bar) VALUES ('foo1', 'bar1')")
        with sqlite3_db.Database(
                _SCHEMA, database_dir=tempdir.name).snapshot() as snapshot:
            self.assertCountEqual(
                (('foo1', 'bar1'),),
                snapshot.execute('SELECT foo, bar FROM Test'),
            )

    def test_foreign_keys_are_enforced(self):
        with self._db.transaction() as transaction:
            transaction.execute(
                "INSERT INTO Test (foo, bar) VALUES ('foo1', 'bar1')")
            transaction.execute(
                "INSERT INTO DependsOnTest (foo) VALUES ('foo1')")
            transaction.execute('DELETE FROM Test')
        with self._db.snapshot() as snapshot:
            self.assertFalse(
                snapshot.execute('SELECT * FROM DependsOnTest').fetchall())

    def test_exception_rolls_back_transaction_and_propagates(self):
        with self.assertRaisesRegex(ValueError, 'this should propagate'):
            with self._db.transaction() as transaction:
                transaction.execute(
                    "INSERT INTO Test (foo, bar) VALUES ('foo1', 'bar1')")
                raise ValueError('this should propagate')
        with self._db.snapshot() as snapshot:
            self.assertFalse(snapshot.execute('SELECT * FROM Test').fetchall())

    def test_reuse_snapshot(self):
        with self._db.snapshot() as snapshot:
            with self._db.snapshot(snapshot) as reused:
                self.assertIs(snapshot, reused)

    def test_reuse_transaction(self):
        with self._db.transaction() as transaction:
            with self._db.transaction(transaction) as reused:
                self.assertIs(transaction, reused)

    def test_case_sensitive_like(self):
        with self._db.snapshot() as snapshot:
            self.assertSequenceEqual(
                (True, False, True, False),
                snapshot.execute("""
                    SELECT
                        'a' LIKE 'a',
                        'a' LIKE 'A',
                        'б' LIKE 'б',
                        'б' LIKE 'Б'
                """).fetchone(),
            )

    def test_reverse_unordered_select(self):
        with self._db.transaction() as transaction:
            transaction.execute("""
                INSERT INTO Test (foo, bar)
                VALUES ('foo1', 'bar1'), ('foo2', 'bar2')
            """)
        with self._db.snapshot() as snapshot:
            normal_order = snapshot.execute(
                'SELECT foo, bar FROM Test').fetchall()
        with self._db_reverse_unordered_select.snapshot() as snapshot:
            reverse_order = snapshot.execute(
                'SELECT foo, bar FROM Test').fetchall()
        self.assertSequenceEqual(normal_order, tuple(reversed(reverse_order)))


class QueryBuilderTest(unittest.TestCase):

    def test_builder(self):
        builder = sqlite3_db.QueryBuilder()
        builder.append('SELECT * FROM Foo')
        builder.append('WHERE a = ?', (1,))
        builder.append('AND b = ?', (2,))
        self.assertEqual(
            ('SELECT * FROM Foo WHERE a = ? AND b = ?', (1, 2)),
            builder.build(),
        )


if __name__ == '__main__':
    unittest.main()
