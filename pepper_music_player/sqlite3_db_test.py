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
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE Test (
                foo TEXT,
                bar TEXT,
                PRIMARY KEY (foo)
            )
            """,
            drop='DROP TABLE IF EXISTS Test',
        ),
        sqlite3_db.SchemaItem('CREATE INDEX Test_BarIndex ON Test (bar)'),
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE DependsOnTest (
                foo TEXT REFERENCES Test (foo) ON DELETE CASCADE
            )
            """,
            drop='DROP TABLE IF EXISTS DependsOnTest',
        ),
    ),
)


class DatabaseTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self._db = sqlite3_db.Database(_SCHEMA, database_dir=tempdir.name)
        self._db.reset()

    def test_reset_deletes_data(self):
        with self._db.transaction() as transaction:
            transaction.execute(
                'INSERT INTO Test (foo, bar) VALUES ("foo1", "bar1")')
            transaction.execute(
                'INSERT INTO DependsOnTest (foo) VALUES ("foo1")')
        self._db.reset()
        with self._db.snapshot() as snapshot:
            self.assertFalse(snapshot.execute('SELECT * FROM Test').fetchall())
            self.assertFalse(
                snapshot.execute('SELECT * FROM DependsOnTest').fetchall())

    def test_foreign_keys_are_enforced(self):
        with self._db.transaction() as transaction:
            transaction.execute(
                'INSERT INTO Test (foo, bar) VALUES ("foo1", "bar1")')
            transaction.execute(
                'INSERT INTO DependsOnTest (foo) VALUES ("foo1")')
            transaction.execute('DELETE FROM Test')
        with self._db.snapshot() as snapshot:
            self.assertFalse(
                snapshot.execute('SELECT * FROM DependsOnTest').fetchall())

    def test_exception_rolls_back_transaction_and_propagates(self):
        with self.assertRaisesRegex(ValueError, 'this should propagate'):
            with self._db.transaction() as transaction:
                transaction.execute(
                    'INSERT INTO Test (foo, bar) VALUES ("foo1", "bar1")')
                raise ValueError('this should propagate')
        with self._db.snapshot() as snapshot:
            self.assertFalse(snapshot.execute('SELECT * FROM Test').fetchall())


if __name__ == '__main__':
    unittest.main()
