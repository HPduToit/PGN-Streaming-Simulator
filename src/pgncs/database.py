"""Database helpers for the PGN simulator."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .configs.settings import settings


def get_default_database_url() -> str:
    configured_database_url = os.getenv("PGN_DATABASE_URL")
    if configured_database_url not in (None, ""):
        return configured_database_url
    return settings.default_sqlite_database_url


DEFAULT_DATABASE_URL = get_default_database_url()


class Database:
    """Small database wrapper supporting SQLite and PostgreSQL URLs."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or DEFAULT_DATABASE_URL
        if self.database_url.startswith("sqlite:///"):
            self.backend = "sqlite"
        elif self.database_url.startswith("postgresql://") or self.database_url.startswith(
            "postgres://"
        ):
            self.backend = "postgres"
        else:
            raise ValueError(
                "Unsupported database URL. Use sqlite:///... or postgresql://..."
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection | object]:
        """Yield a DB connection and commit on success."""
        if self.backend == "sqlite":
            db_path = self.database_url.removeprefix("sqlite:///")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                yield connection
                connection.commit()
            finally:
                connection.close()
            return

        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "psycopg is required for PostgreSQL. Run poetry install first."
            ) from exc

        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
