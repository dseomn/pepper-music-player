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
"""Playlist management."""

import enum
import itertools
from typing import Optional, Sequence
import uuid

import frozendict

from pepper_music_player.library import database
from pepper_music_player.metadata import entity
from pepper_music_player.metadata import token
from pepper_music_player.player import audio
from pepper_music_player import sqlite3_db


# TODO(#20): What are the implications of changing the allowed entity types on
# data format stability? Does the schema version need to be bumped on any change
# to the allowed types? Or can the code be adapted to tolerate type changes
# without version changes?
class _LibraryEntityType(enum.Enum):
    TRACK = 'track'
    MEDIUM = 'medium'
    ALBUM = 'album'


_TOKEN_TYPE_TO_STR = frozendict.frozendict({
    token.Track: _LibraryEntityType.TRACK.value,
    token.Medium: _LibraryEntityType.MEDIUM.value,
    token.Album: _LibraryEntityType.ALBUM.value,
})

_SCHEMA = sqlite3_db.Schema(
    name='playlist',
    version='v1alpha',  # TODO(#20): Change to v1.
    items=(
        # Entry in the playlist.
        #
        # Columns:
        #   token: Token of the entry.
        #   next_token: Next entry in the playlist, or NULL if this is the last
        #       entry.
        #   library_token_type: Type of library entity in this entry, e.g.,
        #       'album' or 'track'.
        #   library_token: Token of the library entity in this entry.
        sqlite3_db.SchemaItem("""
            CREATE TABLE Entry (
                token TEXT NOT NULL,
                next_token TEXT DEFAULT NULL
                    REFERENCES Entry (token) ON DELETE SET DEFAULT
                    DEFERRABLE INITIALLY DEFERRED,
                library_token_type TEXT NOT NULL,
                library_token TEXT NOT NULL,
                PRIMARY KEY (token),
                UNIQUE (next_token)
            )
        """),

        # TODO(dseomn): Keep track of the position in the playlist.
    ),
)


def _new_entry_token() -> token.PlaylistEntry:
    # TODO(#20): Change version to v1.
    return token.PlaylistEntry(f'playlistEntry/v1alpha:{uuid.uuid4()}')


class Playlist:
    """A list of things to play, along with the state of what's playing."""

    def __init__(
            self,
            *,
            player: audio.Player,
            library_db: database.Database,
            database_dir: str,
            reverse_unordered_selects: bool = False,
    ) -> None:
        """Initializer.

        Args:
            player: Audio player to use for playing this playlist.
            library_db: Library database.
            database_dir: Directory containing databases.
            reverse_unordered_selects: For tests only, see sqlite3_db.Database.
        """
        self._db = sqlite3_db.Database(
            _SCHEMA,
            database_dir=database_dir,
            reverse_unordered_selects=reverse_unordered_selects,
        )
        self._player = player
        self._player.set_next_playable_unit_callback(self._next_playable_unit)
        self._library_db = library_db

    def _all_tracks(
            self,
            library_token_type: str,
            library_token: str,
    ) -> Sequence[entity.Track]:
        """Returns all tracks in the given entity, in order.

        Args:
            library_token_type: Type of the entity.
            library_token: Token of the entity.

        Raises:
            KeyError: The entity was not found.
        """
        if library_token_type == _LibraryEntityType.TRACK.value:
            return (self._library_db.track(token.Track(library_token)),)
        elif library_token_type == _LibraryEntityType.MEDIUM.value:
            return self._library_db.medium(token.Medium(library_token)).tracks
        elif library_token_type == _LibraryEntityType.ALBUM.value:
            mediums = self._library_db.album(token.Album(library_token)).mediums
            return tuple(
                itertools.chain.from_iterable(
                    medium.tracks for medium in mediums))
        else:
            raise TypeError(
                f'Unknown library_token_type {library_token_type!r}.')

    def _first_playable_unit(self) -> Optional[audio.PlayableUnit]:
        """Returns the first playable unit, if there is one."""
        with self._db.snapshot() as snapshot:
            row = snapshot.execute("""
                SELECT
                    Entry.token, Entry.library_token_type, Entry.library_token
                FROM Entry
                LEFT JOIN Entry AS PreviousEntry
                    ON PreviousEntry.next_token = Entry.token
                WHERE PreviousEntry.token IS NULL
            """).fetchone()
            if row is None:
                return None
            entry_token, library_token_type, library_token = row
            try:
                track = self._all_tracks(library_token_type, library_token)[0]
            except KeyError:
                return None
            return audio.PlayableUnit(
                track=track,
                playlist_entry_token=token.PlaylistEntry(entry_token))

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _next_playable_unit(
            self,
            playable_unit: Optional[audio.PlayableUnit],
    ) -> Optional[audio.PlayableUnit]:  # yapf: disable
        """See audio.NextPlayableUnitCallback."""
        if playable_unit is None:
            return self._first_playable_unit()
        raise NotImplementedError('TODO(dseomn)')

    def append(self, library_token: token.LibraryToken) -> None:
        """Appends the given token to the playlist."""
        with self._db.transaction() as transaction:
            entry_token = _new_entry_token()
            transaction.execute(
                """
                UPDATE Entry
                SET next_token = ?
                WHERE next_token IS NULL
                """,
                (str(entry_token),),
            )
            transaction.execute(
                """
                INSERT INTO Entry (token, library_token_type, library_token)
                VALUES (?, ?, ?)
                """,
                (
                    str(entry_token),
                    _TOKEN_TYPE_TO_STR[type(library_token)],
                    str(library_token),
                ),
            )
