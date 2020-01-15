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
"""Database for a library."""

import collections
import enum
import itertools
from typing import Generator, Iterable, Optional

import frozendict

from pepper_music_player.library import scan
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import tag
from pepper_music_player.metadata import token
from pepper_music_player import sqlite3_db


class _EntityType(enum.Enum):
    TRACK = 'track'
    MEDIUM = 'medium'
    ALBUM = 'album'


_TYPE_NAME_TO_TOKEN_TYPE = frozendict.frozendict({
    _EntityType.TRACK.value: token.Track,
    _EntityType.MEDIUM.value: token.Medium,
    _EntityType.ALBUM.value: token.Album,
})

_SCHEMA = sqlite3_db.Schema(
    name='library',
    version='v1alpha',  # TODO(#20): Change to v1.
    items=(
        # Files that the entities in the library come from.
        #
        # TODO(dseomn): Add more columns here so that it's possible to update
        # the library efficiently without re-parsing files that are unchanged.
        #
        # Columns:
        #   filename: Absolute filename.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE File (
                filename TEXT NOT NULL,
                PRIMARY KEY (filename)
            )
            """,
            drop='DROP TABLE IF EXISTS File',
        ),

        # Entities in the library, e.g., tracks, mediums, and albums.
        #
        # TODO(dseomn): Add a trigger to delete an entity when it has no
        # filename and no children?
        #
        # Columns:
        #   token: Opaque token identifying the entity.
        #   type  Type of the entity, see _EntityType above. (The colon after
        #       'type' in this comment is intentionally missing to prevent
        #       pylint and pytype from interpreting this as a type annotation
        #       comment.)
        #   filename: File the entity came from, or NULL if the entity doesn't
        #       correspond directly to a single file.
        #   parent_token: Token of the entity that contains this entity, or NULL
        #       if this is a top-level entity.
        #   order_in_parent: Order of this entity within the parent, e.g., a
        #       tracknumber or discnumber. Or NULL if this doesn't have a
        #       defined order or doesn't have a parent. Note that this is not
        #       guaranteed to be unique within the parent.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE Entity (
                token TEXT NOT NULL,
                type TEXT NOT NULL,
                filename TEXT REFERENCES File (filename) ON DELETE CASCADE,
                parent_token TEXT REFERENCES Entity (token) ON DELETE CASCADE,
                order_in_parent INTEGER,
                PRIMARY KEY (token),
                UNIQUE (filename)
            )
            """,
            drop='DROP TABLE IF EXISTS Entity',
        ),
        sqlite3_db.SchemaItem("""
            CREATE INDEX Entity_ParentIndex
            ON Entity (parent_token, order_in_parent)
        """),

        # Tags for entities in the library.
        #
        # Columns:
        #   token: Token of the entity with tags.
        #   tag_name: Name of the tag, e.g., 'artist'. Each value may appear
        #       multiple times for the same token.
        #   tag_value: A single value for the tag.
        sqlite3_db.SchemaItem(
            """
            CREATE TABLE Tag (
                token TEXT NOT NULL REFERENCES Entity (token) ON DELETE CASCADE,
                tag_name TEXT NOT NULL,
                tag_value TEXT NOT NULL
            )
            """,
            drop='DROP TABLE IF EXISTS Tag',
        ),
        sqlite3_db.SchemaItem('CREATE INDEX Tag_TokenIndex ON Tag (token)'),
        sqlite3_db.SchemaItem(
            'CREATE INDEX Tag_TagIndex ON Tag (tag_name, tag_value)'),
    ),
)


class Database:
    """Database for a library."""

    # TODO(dseomn): Add support for incremental updates instead of resetting and
    # re-adding everything each time. As part of incremental updates, it might
    # make sense to add a pubsub-like system so the database can publish tokens
    # that have been added/deleted or that have modified data. Subscribers could
    # then react accordingly without needing to poll the database.

    def __init__(
            self,
            *,
            database_dir: str,
    ) -> None:
        """Initializer.

        Args:
            database_dir: Directory containing databases.
        """
        self._db = sqlite3_db.Database(_SCHEMA, database_dir=database_dir)

    def reset(self) -> None:
        """(Re)sets the library to its initial, empty state."""
        self._db.reset()

    def _get_tags(
            self,
            snapshot: sqlite3_db.AbstractSnapshot,
            token_: str,
    ) -> tag.Tags:
        """Returns Tags for the given token."""
        tags = collections.defaultdict(list)
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for name, value in snapshot.execute(
                'SELECT tag_name, tag_value FROM Tag WHERE token = ?',
                (token_,)):  # yapf: disable
            tags[name].append(value)
        return tag.Tags(tags)

    def _set_tags(
            self,
            transaction: sqlite3_db.Transaction,
            token_: str,
            tags: tag.Tags,
    ) -> None:
        """Sets Tags for the given token."""
        transaction.execute('DELETE FROM Tag WHERE token = ?', (token_,))
        for name, values in tags.items():
            transaction.executemany(
                'INSERT INTO Tag (token, tag_name, tag_value) VALUES (?, ?, ?)',
                ((token_, name, value) for value in values),
            )

    def _insert_audio_file(
            self,
            transaction: sqlite3_db.Transaction,
            file_info: scan.AudioFile,
    ) -> None:
        """Inserts information about the given audio file.

        Args:
            transaction: Transaction to use.
            file_info: File to insert.
        """
        track_token = str(file_info.track.token)
        medium_token = str(file_info.track.medium_token)
        album_token = str(file_info.track.album_token)
        transaction.executemany(
            """
            INSERT OR IGNORE INTO Entity
                (token, type, filename, parent_token, order_in_parent)
            VALUES (:token, :type, :filename, :parent_token, :order_in_parent)
            """,
            (
                {
                    'token': album_token,
                    'type': _EntityType.ALBUM.value,
                    'filename': None,
                    'parent_token': None,
                    'order_in_parent': None,
                },
                {
                    'token':
                        medium_token,
                    'type':
                        _EntityType.MEDIUM.value,
                    'filename':
                        None,
                    'parent_token':
                        album_token,
                    # Note that this relies on all tracks in a medium having the
                    # same PARSED_DISCNUMBER. That's currently enforced by the
                    # medium token including the PARSED_DISCNUMBER; if it ever
                    # changes, this will become buggy since the order_in_parent
                    # will depend on the order the tracks are inserted into the
                    # database.
                    'order_in_parent':
                        file_info.track.tags.int_or_none(tag.PARSED_DISCNUMBER),
                },
                {
                    'token':
                        track_token,
                    'type':
                        _EntityType.TRACK.value,
                    'filename':
                        file_info.filename,
                    'parent_token':
                        medium_token,
                    'order_in_parent':
                        file_info.track.tags.int_or_none(
                            # TODO(https://github.com/google/yapf/issues/797):
                            # Remove this TODO comment.
                            tag.PARSED_TRACKNUMBER),
                },
            ),
        )
        self._set_tags(transaction, track_token, file_info.track.tags)

    def _compose_tags(
            self,
            transaction: sqlite3_db.Transaction,
            *,
            child_type: _EntityType,
    ) -> None:
        """Updates tags of parent entities based on their children's tags.

        Args:
            transaction: Transaction to use.
            child_type: Which type of entity to update the parent's tags of.
        """
        for parent_token, rows in itertools.groupby(
                transaction.execute(
                    """
                    SELECT parent_token, token
                    FROM Entity
                    WHERE type = ?
                    ORDER BY parent_token
                    """,
                    (child_type.value,),
                ),
                lambda row: row[0],
        ):
            self._set_tags(
                transaction,
                parent_token,
                tag.compose(
                    self._get_tags(transaction, child_token)
                    for _, child_token in rows),
            )

    def insert_files(self, files: Iterable[scan.File]) -> None:
        """Inserts information about the given files.

        Args:
            files: Files to insert into the database.

        Raises:
            sqlite3.IntegrityError: One or more files are already in the
                database.
        """
        # TODO(dseomn): Break this up into many smaller transactions, so that
        # the user gets more feedback when (re)scanning the library.
        with self._db.transaction() as transaction:
            for file_info in files:
                transaction.execute('INSERT INTO File (filename) VALUES (?)',
                                    (file_info.filename,))
                if isinstance(file_info, scan.AudioFile):
                    self._insert_audio_file(transaction, file_info)
            self._compose_tags(transaction, child_type=_EntityType.TRACK)
            self._compose_tags(transaction, child_type=_EntityType.MEDIUM)

    def search(self) -> Iterable[token.LibraryToken]:
        """Searches for music in the library.

        TODO(dseomn): Add more function arguments to make this actually search
        instead of returning everything.

        Returns:
            Tokens for entities that match the search terms.
        """
        # This returns a list instead of a generator to avoid bugs with nested
        # transactions, which sqlite3 doesn't support. With a generator, a loop
        # like this would fail because the inner access would try to start a
        # nested transaction:
        #
        #   for result in db.search()
        #       if isinstance(result, token.Track):
        #           db.track(result)
        results = []
        with self._db.snapshot() as snapshot:
            for token_str, token_type in snapshot.execute(
                    'SELECT token, type FROM Entity'):
                results.append(_TYPE_NAME_TO_TOKEN_TYPE[token_type](token_str))
        return results

    def _require_token_exists(
            self,
            snapshot: sqlite3_db.AbstractSnapshot,
            token_: str,
            token_type: _EntityType,
    ) -> None:
        """Raises KeyError if the specified token does not exist."""
        # TODO(dseomn): Optimize callers of this function to avoid calling it
        # when they got the token from the database in the same transaction.
        if snapshot.execute('SELECT 1 FROM Entity WHERE token = ? AND type = ?',
                            (token_, token_type.value)).fetchone() is None:
            raise KeyError(token_)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _children(
            self,
            snapshot: sqlite3_db.AbstractSnapshot,
            token_: str,
            *,
            child_type: _EntityType,
    ) -> Generator[token.LibraryToken, None, None]:  # yapf: disable
        """Yields the given token's child tokens, in order."""
        # TODO(https://github.com/google/yapf/issues/792): Remove yapf disable.
        for (child_token,) in snapshot.execute(
                """
                SELECT token
                FROM Entity
                WHERE parent_token = ? AND type = ?
                ORDER BY order_in_parent, token
                """,
                (token_, child_type.value),
        ):  # yapf: disable
            yield _TYPE_NAME_TO_TOKEN_TYPE[child_type.value](child_token)

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def track(
            self,
            token_: token.Track,
            *,
            snapshot: Optional[sqlite3_db.AbstractSnapshot] = None,
    ) -> entity.Track:  # yapf: disable
        """Returns the specified track.

        Args:
            token_: Which track to return.
            snapshot: Snapshot to reuse instead of starting a new one.

        Raises:
            KeyError: There's no track with the given token.
        """
        with self._db.snapshot(snapshot) as snapshot_:
            self._require_token_exists(snapshot_, str(token_),
                                       _EntityType.TRACK)
            # TODO(dseomn): Do something if the returned token is different?
            return entity.Track(tags=self._get_tags(snapshot_, str(token_)))

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def medium(
            self,
            token_: token.Medium,
            *,
            snapshot: Optional[sqlite3_db.AbstractSnapshot] = None,
    ) -> entity.Medium:  # yapf: disable
        """Returns the specified medium.

        Args:
            token_: Which medium to return.
            snapshot: Snapshot to reuse instead of starting a new one.

        Raises:
            KeyError: There's no medium with the given token.
        """
        with self._db.snapshot(snapshot) as snapshot_:
            self._require_token_exists(snapshot_, str(token_),
                                       _EntityType.MEDIUM)
            track_token_generator = self._children(snapshot_,
                                                   str(token_),
                                                   child_type=_EntityType.TRACK)
            # TODO(dseomn): Do something if the returned token is different?
            return entity.Medium(
                tags=self._get_tags(snapshot_, str(token_)),
                tracks=tuple(
                    self.track(track_token, snapshot=snapshot_)
                    for track_token in track_token_generator),
            )

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def album(
            self,
            token_: token.Album,
            *,
            snapshot: Optional[sqlite3_db.AbstractSnapshot] = None,
    ) -> entity.Album:  # yapf: disable
        """Returns the specified album.

        Args:
            token_: Which album to return.
            snapshot: Snapshot to reuse instead of starting a new one.

        Raises:
            KeyError: There's no album with the given token.
        """
        with self._db.snapshot(snapshot) as snapshot_:
            self._require_token_exists(snapshot_, str(token_),
                                       _EntityType.ALBUM)
            medium_token_generator = self._children(
                snapshot_, str(token_), child_type=_EntityType.MEDIUM)
            # TODO(dseomn): Do something if the returned token is different?
            return entity.Album(
                tags=self._get_tags(snapshot_, str(token_)),
                mediums=tuple(
                    self.medium(medium_token, snapshot=snapshot_)
                    for medium_token in medium_token_generator),
            )
