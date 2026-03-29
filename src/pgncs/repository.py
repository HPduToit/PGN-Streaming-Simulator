"""Persistence layer for stored simulator tournaments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import BaseSettings
from .database import Database
from .dbdef import create_tables as create_postgres_tables
from .dbdef import reset_tables as reset_postgres_tables


def utc_now_iso() -> str:
    """Return a UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StoredTournament:
    """Persisted tournament configuration and lifecycle."""

    code: str
    settings: BaseSettings
    status: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    last_error: str | None
    run_revision: int


@dataclass
class StoredGame:
    """Persisted board snapshot."""

    tournament_code: str
    round_no: int
    board_no: int
    payload: dict[str, Any]
    pgn_text: str
    is_finished: bool
    updated_at: str


class TournamentRepository:
    """CRUD operations for tournaments and board snapshots."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def init_db(self) -> None:
        """Create required tables if they do not exist."""
        if self.database.backend == "postgres":
            create_postgres_tables()
            return

        with self.database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tournaments (
                    code TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    last_error TEXT,
                    run_revision INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tournament_games (
                    tournament_code TEXT NOT NULL,
                    round_no INTEGER NOT NULL,
                    board_no INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    pgn_text TEXT NOT NULL,
                    is_finished INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tournament_code, round_no, board_no),
                    FOREIGN KEY(tournament_code) REFERENCES tournaments(code) ON DELETE CASCADE
                )
                """
            )
            self._ensure_tournament_columns(cursor)

    def reset_db(self) -> None:
        """Drop and recreate simulator tables."""
        if self.database.backend == "postgres":
            reset_postgres_tables()
            return

        with self.database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("DROP TABLE IF EXISTS tournament_games")
            cursor.execute("DROP TABLE IF EXISTS tournaments")
        self.init_db()

    def create_tournament(self, settings: BaseSettings) -> str:
        """Persist a new tournament and return its generated code."""
        code = str(uuid4())
        created_at = utc_now_iso()
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._insert_tournament_sql(
                code,
                json.dumps(settings.to_dict()),
                "created",
                created_at,
            )
            cursor.execute(query, params)
        return code

    def get_tournament(self, code: str) -> StoredTournament | None:
        """Fetch one tournament."""
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._select_tournament_sql(code)
            cursor.execute(query, params)
            row = cursor.fetchone()
        return None if row is None else self._to_tournament(row)

    def list_tournaments(self) -> list[StoredTournament]:
        """Fetch all tournaments."""
        with self.database.connect() as connection:
            cursor = connection.cursor()
            if self.database.backend == "sqlite":
                cursor.execute("SELECT * FROM tournaments ORDER BY created_at ASC")
            else:
                cursor.execute("SELECT * FROM tournaments ORDER BY created_at ASC")
            rows = cursor.fetchall()
        return [self._to_tournament(row) for row in rows]

    def list_tournaments_by_status(self, status: str) -> list[StoredTournament]:
        """Fetch all tournaments with the provided status."""
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._list_tournaments_by_status_sql(status)
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [self._to_tournament(row) for row in rows]

    def update_tournament(self, code: str, settings: BaseSettings) -> None:
        """Replace the stored config for an existing non-running tournament."""
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._update_tournament_sql(code, json.dumps(settings.to_dict()))
            cursor.execute(query, params)
            if cursor.rowcount == 0:
                raise KeyError(f"Tournament not found or currently running: {code}")

    def mark_tournament_running(self, code: str) -> None:
        """Move a tournament into running state."""
        now = utc_now_iso()
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._mark_running_sql(code, now)
            cursor.execute(query, params)
            if cursor.rowcount == 0:
                raise KeyError(f"Tournament not found: {code}")

    def mark_tournament_stopped(self, code: str) -> None:
        """Move a tournament into stopped state."""
        now = utc_now_iso()
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._mark_stopped_sql(code, now)
            cursor.execute(query, params)
            if cursor.rowcount == 0:
                raise KeyError(f"Tournament not found: {code}")

    def mark_tournament_finished(self, code: str) -> None:
        """Mark a tournament as finished."""
        now = utc_now_iso()
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._mark_finished_sql(code, now)
            cursor.execute(query, params)

    def mark_tournament_failed(self, code: str, error_message: str) -> None:
        """Mark a tournament as failed."""
        now = utc_now_iso()
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._mark_failed_sql(code, now, error_message)
            cursor.execute(query, params)

    def upsert_game_snapshot(
        self,
        tournament_code: str,
        round_no: int,
        board_no: int,
        payload: dict[str, Any],
        pgn_text: str,
        is_finished: bool,
    ) -> None:
        """Store the latest snapshot for a board."""
        updated_at = utc_now_iso()
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._upsert_game_sql(
                tournament_code=tournament_code,
                round_no=round_no,
                board_no=board_no,
                payload_json=json.dumps(payload),
                pgn_text=pgn_text,
                is_finished=is_finished,
                updated_at=updated_at,
            )
            cursor.execute(query, params)

    def clear_game_snapshots(
        self,
        tournament_code: str,
        round_no: int | None = None,
    ) -> None:
        """Delete persisted snapshots for a tournament, optionally scoped to one round."""
        with self.database.connect() as connection:
            cursor = connection.cursor()
            if round_no is None:
                if self.database.backend == "sqlite":
                    cursor.execute(
                        "DELETE FROM tournament_games WHERE tournament_code = ?",
                        (tournament_code,),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM tournament_games WHERE tournament_code = %s",
                        (tournament_code,),
                    )
                return

            if self.database.backend == "sqlite":
                cursor.execute(
                    "DELETE FROM tournament_games WHERE tournament_code = ? AND round_no = ?",
                    (tournament_code, round_no),
                )
            else:
                cursor.execute(
                    "DELETE FROM tournament_games WHERE tournament_code = %s AND round_no = %s",
                    (tournament_code, round_no),
                )

    def list_game_snapshots(
        self,
        tournament_code: str,
        round_no: int,
    ) -> list[StoredGame]:
        """Fetch all board snapshots for a round."""
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._list_games_sql(tournament_code, round_no)
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [self._to_game(row) for row in rows]

    def get_game_snapshot(
        self,
        tournament_code: str,
        round_no: int,
        board_no: int,
    ) -> StoredGame | None:
        """Fetch one board snapshot."""
        with self.database.connect() as connection:
            cursor = connection.cursor()
            query, params = self._select_game_sql(tournament_code, round_no, board_no)
            cursor.execute(query, params)
            row = cursor.fetchone()
        return None if row is None else self._to_game(row)

    def _to_tournament(self, row: Any) -> StoredTournament:
        data = dict(row)
        return StoredTournament(
            code=data["code"],
            settings=BaseSettings.from_dict(json.loads(data["config_json"])),
            status=data["status"],
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            last_error=data.get("last_error"),
            run_revision=int(data.get("run_revision", 0)),
        )

    def _to_game(self, row: Any) -> StoredGame:
        data = dict(row)
        return StoredGame(
            tournament_code=data["tournament_code"],
            round_no=int(data["round_no"]),
            board_no=int(data["board_no"]),
            payload=json.loads(data["payload_json"]),
            pgn_text=data["pgn_text"],
            is_finished=bool(data["is_finished"]),
            updated_at=data["updated_at"],
        )

    def _insert_tournament_sql(
        self,
        code: str,
        config_json: str,
        status: str,
        created_at: str,
    ) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                "INSERT INTO tournaments (code, config_json, status, created_at) VALUES (?, ?, ?, ?)",
                (code, config_json, status, created_at),
            )
        return (
            "INSERT INTO tournaments (code, config_json, status, created_at) VALUES (%s, %s, %s, %s)",
            (code, config_json, status, created_at),
        )

    def _select_tournament_sql(self, code: str) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return ("SELECT * FROM tournaments WHERE code = ?", (code,))
        return ("SELECT * FROM tournaments WHERE code = %s", (code,))

    def _list_tournaments_by_status_sql(self, status: str) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return ("SELECT * FROM tournaments WHERE status = ? ORDER BY created_at ASC", (status,))
        return ("SELECT * FROM tournaments WHERE status = %s ORDER BY created_at ASC", (status,))

    def _mark_running_sql(self, code: str, now: str) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                """
                UPDATE tournaments
                SET status = ?, started_at = ?, finished_at = NULL, last_error = NULL, run_revision = run_revision + 1
                WHERE code = ?
                """,
                ("running", now, code),
            )
        return (
            """
            UPDATE tournaments
            SET status = %s, started_at = %s, finished_at = NULL, last_error = NULL, run_revision = run_revision + 1
            WHERE code = %s
            """,
            ("running", now, code),
        )

    def _update_tournament_sql(self, code: str, config_json: str) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                """
                UPDATE tournaments
                SET config_json = ?, status = ?, started_at = NULL, finished_at = NULL, last_error = NULL
                WHERE code = ? AND status != ?
                """,
                (config_json, "created", code, "running"),
            )
        return (
            """
            UPDATE tournaments
            SET config_json = %s, status = %s, started_at = NULL, finished_at = NULL, last_error = NULL
            WHERE code = %s AND status != %s
            """,
            (config_json, "created", code, "running"),
        )

    def _mark_stopped_sql(self, code: str, now: str) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                """
                UPDATE tournaments
                SET status = ?, finished_at = ?, last_error = NULL, run_revision = run_revision + 1
                WHERE code = ?
                """,
                ("stopped", now, code),
            )
        return (
            """
            UPDATE tournaments
            SET status = %s, finished_at = %s, last_error = NULL, run_revision = run_revision + 1
            WHERE code = %s
            """,
            ("stopped", now, code),
        )

    def _mark_finished_sql(self, code: str, now: str) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                "UPDATE tournaments SET status = ?, finished_at = ?, last_error = NULL WHERE code = ?",
                ("finished", now, code),
            )
        return (
            "UPDATE tournaments SET status = %s, finished_at = %s, last_error = NULL WHERE code = %s",
            ("finished", now, code),
        )

    def _mark_failed_sql(
        self,
        code: str,
        now: str,
        error_message: str,
    ) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                "UPDATE tournaments SET status = ?, finished_at = ?, last_error = ? WHERE code = ?",
                ("failed", now, error_message, code),
            )
        return (
            "UPDATE tournaments SET status = %s, finished_at = %s, last_error = %s WHERE code = %s",
            ("failed", now, error_message, code),
        )

    def _ensure_tournament_columns(self, cursor: Any) -> None:
        """Backfill newer columns into an existing tournaments table."""
        if self.database.backend == "sqlite":
            cursor.execute("PRAGMA table_info(tournaments)")
            columns = {row[1] for row in cursor.fetchall()}
            if "run_revision" not in columns:
                cursor.execute(
                    "ALTER TABLE tournaments ADD COLUMN run_revision INTEGER NOT NULL DEFAULT 0"
                )
            return

        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tournaments'
            """
        )
        columns = {row["column_name"] for row in cursor.fetchall()}
        if "run_revision" not in columns:
            cursor.execute(
                "ALTER TABLE tournaments ADD COLUMN run_revision INTEGER NOT NULL DEFAULT 0"
            )

    def _upsert_game_sql(
        self,
        tournament_code: str,
        round_no: int,
        board_no: int,
        payload_json: str,
        pgn_text: str,
        is_finished: bool,
        updated_at: str,
    ) -> tuple[str, tuple[Any, ...]]:
        finished_flag = int(is_finished)
        if self.database.backend == "sqlite":
            return (
                """
                INSERT INTO tournament_games (
                    tournament_code, round_no, board_no, payload_json, pgn_text, is_finished, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tournament_code, round_no, board_no)
                DO UPDATE SET
                    payload_json = excluded.payload_json,
                    pgn_text = excluded.pgn_text,
                    is_finished = excluded.is_finished,
                    updated_at = excluded.updated_at
                """,
                (
                    tournament_code,
                    round_no,
                    board_no,
                    payload_json,
                    pgn_text,
                    finished_flag,
                    updated_at,
                ),
            )
        return (
            """
            INSERT INTO tournament_games (
                tournament_code, round_no, board_no, payload_json, pgn_text, is_finished, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tournament_code, round_no, board_no)
            DO UPDATE SET
                payload_json = EXCLUDED.payload_json,
                pgn_text = EXCLUDED.pgn_text,
                is_finished = EXCLUDED.is_finished,
                updated_at = EXCLUDED.updated_at
            """,
            (
                tournament_code,
                round_no,
                board_no,
                payload_json,
                pgn_text,
                finished_flag,
                updated_at,
            ),
        )

    def _list_games_sql(
        self,
        tournament_code: str,
        round_no: int,
    ) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                """
                SELECT * FROM tournament_games
                WHERE tournament_code = ? AND round_no = ?
                ORDER BY board_no ASC
                """,
                (tournament_code, round_no),
            )
        return (
            """
            SELECT * FROM tournament_games
            WHERE tournament_code = %s AND round_no = %s
            ORDER BY board_no ASC
            """,
            (tournament_code, round_no),
        )

    def _select_game_sql(
        self,
        tournament_code: str,
        round_no: int,
        board_no: int,
    ) -> tuple[str, tuple[Any, ...]]:
        if self.database.backend == "sqlite":
            return (
                """
                SELECT * FROM tournament_games
                WHERE tournament_code = ? AND round_no = ? AND board_no = ?
                """,
                (tournament_code, round_no, board_no),
            )
        return (
            """
            SELECT * FROM tournament_games
            WHERE tournament_code = %s AND round_no = %s AND board_no = %s
            """,
            (tournament_code, round_no, board_no),
        )
