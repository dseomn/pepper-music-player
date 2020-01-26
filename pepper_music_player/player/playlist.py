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

_STR_TO_TOKEN_TYPE = frozendict.frozendict(
    {value: key for key, value in _TOKEN_TYPE_TO_STR.items()})

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
            entry: entity.PlaylistEntry,
    ) -> Sequence[entity.Track]:
        """Returns all tracks for the given entry, in order.

        Args:
            entry: Entry to get all the tracks of.

        Raises:
            KeyError: The library entity was not found.
        """
        if isinstance(entry.library_token, token.Track):
            return (self._library_db.track(entry.library_token),)
        elif isinstance(entry.library_token, token.Medium):
            return self._library_db.medium(entry.library_token).tracks
        elif isinstance(entry.library_token, token.Album):
            mediums = self._library_db.album(entry.library_token).mediums
            return tuple(
                itertools.chain.from_iterable(
                    medium.tracks for medium in mediums))
        else:
            raise TypeError(
                f'Unknown library token type: {entry.library_token}')

    def _next_entry(
            self,
            entry_token: Optional[token.PlaylistEntry],
            *,
            snapshot: sqlite3_db.AbstractSnapshot,
    ) -> entity.PlaylistEntry:
        """Returns the next entry.

        Args:
            entry_token: Token of the entry before the one that will be
                returned, or None to return the first entry.
            snapshot: Database snapshot.

        Raises:
            LookupError: There is no next entry.
        """
        row = snapshot.execute(
            """
            SELECT Entry.token, Entry.library_token_type, Entry.library_token
            FROM Entry
            LEFT JOIN Entry AS PreviousEntry
                ON PreviousEntry.next_token = Entry.token
            WHERE PreviousEntry.token IS ?
            """,
            (None if entry_token is None else str(entry_token),),
        ).fetchone()
        if row is None:
            if entry_token is None:
                raise LookupError('There is no first entry.')
            else:
                raise LookupError(
                    f"Either {entry_token} doesn't exist, or it's at the end.")
        next_entry_token, library_token_type, library_token = row
        return entity.PlaylistEntry(
            token=token.PlaylistEntry(next_entry_token),
            library_token=_STR_TO_TOKEN_TYPE[library_token_type](library_token),
        )

    # TODO(https://github.com/google/yapf/issues/793): Remove yapf disable.
    def _next_playable_unit(
            self,
            playable_unit: Optional[audio.PlayableUnit],
    ) -> Optional[audio.PlayableUnit]:  # yapf: disable
        """See audio.NextPlayableUnitCallback."""
        # TODO(dseomn): Support modes other than linear playback, e.g., shuffle,
        # repeat track, and repeat all.
        with self._db.snapshot() as snapshot:
            if playable_unit is None:
                try:
                    entry = self._next_entry(None, snapshot=snapshot)
                    return audio.PlayableUnit(
                        track=self._all_tracks(entry)[0],
                        playlist_entry=entry,
                    )
                except LookupError:
                    return None
            try:
                all_tracks = self._all_tracks(playable_unit.playlist_entry)
                track_index = {
                    track.token: index for index, track in enumerate(all_tracks)
                }[playable_unit.track.token]
            except LookupError:
                return None
            if track_index + 1 < len(all_tracks):
                return audio.PlayableUnit(
                    track=all_tracks[track_index + 1],
                    playlist_entry=playable_unit.playlist_entry)
            try:
                entry = self._next_entry(playable_unit.playlist_entry.token,
                                         snapshot=snapshot)
                return audio.PlayableUnit(
                    track=self._all_tracks(entry)[0],
                    playlist_entry=entry,
                )
            except LookupError:
                return None

    def append(self, library_token: token.LibraryToken) -> entity.PlaylistEntry:
        """Appends the given token to the playlist.

        Args:
            library_token: What to append to the playlist.

        Returns:
            The newly added entry.
        """
        with self._db.transaction() as transaction:
            entry = entity.PlaylistEntry(library_token=library_token)
            transaction.execute(
                """
                UPDATE Entry
                SET next_token = ?
                WHERE next_token IS NULL
                """,
                (str(entry.token),),
            )
            transaction.execute(
                """
                INSERT INTO Entry (token, library_token_type, library_token)
                VALUES (?, ?, ?)
                """,
                (
                    str(entry.token),
                    _TOKEN_TYPE_TO_STR[type(library_token)],
                    str(library_token),
                ),
            )
            return entry
