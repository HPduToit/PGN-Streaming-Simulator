from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from pgncs.database import Database
from pgncs.dbdef import get_db_uri
from pgncs.dbdef import get_root_uri
from pgncs.repository import TournamentRepository


class TestDbdef(unittest.TestCase):
    def test_get_db_uri_uses_standardized_env_names(self) -> None:
        with patch.dict(
            os.environ,
            {
                "INSTALLER_USERID": "rtinstall",
                "INSTALLER_PWD": "secret",
                "PGNSS_MYSQL_HOST": "db.internal",
                "PGNSS_MYSQL_TCP_PORT": "5544",
                "PGNSS_MYSQL_DATABASE": "pgnss_db",
            },
            clear=True,
        ):
            self.assertEqual(
                get_db_uri(),
                "postgresql://rtinstall:secret@db.internal:5544/pgnss_db",
            )

    def test_get_db_uri_accepts_legacy_aliases(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PGNSS_POSTGRES_USER": "legacy_user",
                "PGNSS_POSTGRES_PASSWORD": "legacy_password",
                "PGNSS_POSTGRES_PORT": "6000",
                "PGNSS_POSTGRES_DB": "legacy_db",
            },
            clear=True,
        ):
            self.assertEqual(
                get_db_uri(),
                "postgresql://legacy_user:legacy_password@127.0.0.1:6000/legacy_db",
            )
            self.assertEqual(
                get_root_uri(),
                "postgresql://legacy_user:legacy_password@127.0.0.1:6000/postgres",
            )

    def test_sqlite_repository_init_and_reset_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Database(f"sqlite:///{tmpdir}/test.db")
            repository = TournamentRepository(database)

            repository.init_db()
            self.assertEqual(database.backend, "sqlite")

            with database.connect() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in cursor.fetchall()}

            self.assertTrue({"tournaments", "tournament_games"}.issubset(tables))

            repository.reset_db()

            with database.connect() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                reset_tables = {row[0] for row in cursor.fetchall()}

            self.assertTrue({"tournaments", "tournament_games"}.issubset(reset_tables))


if __name__ == "__main__":
    unittest.main()
