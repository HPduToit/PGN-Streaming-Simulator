"""Database bootstrap helpers for the PGN simulator."""

from __future__ import annotations

from pgncs.configs.settings import settings

POSTGRES_MAINTENANCE_DB = "postgres"
EXPECTED_TABLES = {"tournaments", "tournament_games"}


def _connect(*args, **kwargs):
    try:
        from psycopg import connect
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only in lean envs
        raise RuntimeError("psycopg is required for PostgreSQL bootstrap. Run poetry install first.") from exc

    return connect(*args, **kwargs)


def _dict_row():
    try:
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only in lean envs
        raise RuntimeError("psycopg is required for PostgreSQL bootstrap. Run poetry install first.") from exc

    return dict_row


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _postgres_uri(*, username: str, password: str, host: str, port: int, database: str) -> str:
    return f"postgresql://{username}:{password}@{host}:{port}/{database}"


def get_db_uri() -> str:
    return _postgres_uri(
        username=settings.INSTALLER_USERID,
        password=settings.INSTALLER_PWD,
        host=settings.PGNSS_MYSQL_HOST,
        port=settings.PGNSS_MYSQL_TCP_PORT,
        database=settings.PGNSS_MYSQL_DATABASE,
    )


def get_root_uri(database: str = POSTGRES_MAINTENANCE_DB) -> str:
    return _postgres_uri(
        username=settings.MYSQL_ROOT_USER,
        password=settings.MYSQL_ROOT_PASSWORD,
        host=settings.PGNSS_MYSQL_HOST,
        port=settings.PGNSS_MYSQL_TCP_PORT,
        database=database,
    )


def installer_role_exists() -> bool:
    with _connect(get_root_uri(), row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (settings.INSTALLER_USERID,))
            return cursor.fetchone() is not None


def database_exists() -> bool:
    with _connect(get_root_uri(), row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.PGNSS_MYSQL_DATABASE,))
            return cursor.fetchone() is not None


def ensure_installer_role() -> None:
    quoted_role = _quote_identifier(settings.INSTALLER_USERID)
    quoted_password = _quote_literal(settings.INSTALLER_PWD)
    with _connect(get_root_uri(), autocommit=True, row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
            if installer_role_exists():
                cursor.execute(f"ALTER ROLE {quoted_role} WITH LOGIN PASSWORD {quoted_password}")
                print(f"Updated installer role '{settings.INSTALLER_USERID}'.")
            else:
                cursor.execute(f"CREATE ROLE {quoted_role} WITH LOGIN PASSWORD {quoted_password}")
                print(f"Created installer role '{settings.INSTALLER_USERID}'.")


def ensure_database() -> None:
    quoted_database = _quote_identifier(settings.PGNSS_MYSQL_DATABASE)
    quoted_installer = _quote_identifier(settings.INSTALLER_USERID)
    with _connect(get_root_uri(), autocommit=True, row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
            if not database_exists():
                cursor.execute(f"CREATE DATABASE {quoted_database} OWNER {quoted_installer}")
                print(f"Created database '{settings.PGNSS_MYSQL_DATABASE}'.")
            else:
                print(f"Database '{settings.PGNSS_MYSQL_DATABASE}' already exists.")
            cursor.execute(f"ALTER DATABASE {quoted_database} OWNER TO {quoted_installer}")
            cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {quoted_database} TO {quoted_installer}")


def ensure_database_permissions() -> None:
    quoted_installer = _quote_identifier(settings.INSTALLER_USERID)
    with _connect(get_root_uri(settings.PGNSS_MYSQL_DATABASE), autocommit=True, row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER SCHEMA public OWNER TO {quoted_installer}")
            cursor.execute(f"GRANT ALL ON SCHEMA public TO {quoted_installer}")
            cursor.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {quoted_installer}")
            cursor.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {quoted_installer}")


def tables_exist() -> bool:
    with _connect(get_db_uri(), row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
            existing_tables = {row["table_name"] for row in cursor.fetchall()}
    return EXPECTED_TABLES.issubset(existing_tables)


def _ensure_tournaments_columns(cursor) -> None:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tournaments'
        """
    )
    existing_columns = {row["column_name"] for row in cursor.fetchall()}
    if "run_revision" not in existing_columns:
        cursor.execute("ALTER TABLE tournaments ADD COLUMN run_revision INTEGER NOT NULL DEFAULT 0")


def create_tables() -> None:
    with _connect(get_db_uri(), row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
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
                    is_finished BOOLEAN NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tournament_code, round_no, board_no),
                    CONSTRAINT fk_tournament_games_tournament
                        FOREIGN KEY(tournament_code) REFERENCES tournaments(code) ON DELETE CASCADE
                )
                """
            )
            _ensure_tournaments_columns(cursor)
        connection.commit()


def reset_tables() -> None:
    with _connect(get_db_uri(), row_factory=_dict_row()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS tournament_games")
            cursor.execute("DROP TABLE IF EXISTS tournaments")
        connection.commit()
    create_tables()


def initialize_database() -> None:
    ensure_installer_role()
    ensure_database()
    ensure_database_permissions()
    create_tables()


if __name__ == "__main__":
    initialize_database()
