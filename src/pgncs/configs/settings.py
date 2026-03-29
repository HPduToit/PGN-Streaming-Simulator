"""Environment-backed settings for PGN simulator database bootstrap."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - fallback for lean test envs
    def load_dotenv() -> bool:
        return False

load_dotenv()


def _first_non_empty(*names: str, fallback: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return fallback


def _first_non_empty_int(*names: str, fallback: int) -> int:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return int(value)
    return fallback


@dataclass(frozen=True)
class EnvironmentSettings:
    INSTALLER_PWD: str
    INSTALLER_USERID: str
    MYSQL_ROOT_PASSWORD: str
    MYSQL_ROOT_USER: str
    PGNSS_MYSQL_DATABASE: str
    PGNSS_MYSQL_HOST: str
    PGNSS_MYSQL_TCP_PORT: int


class Settings:
    """Resolve the standardized PGN simulator database settings."""

    @property
    def env(self) -> EnvironmentSettings:
        installer_user = _first_non_empty(
            "INSTALLER_USERID",
            "PGNSS_MYSQL_USER",
            "PGNSS_POSTGRES_USER",
            "PGN_POSTGRES_USER",
            fallback="postgres",
        )
        installer_password = _first_non_empty(
            "INSTALLER_PWD",
            "PGNSS_MYSQL_PASSWORD",
            "PGNSS_POSTGRES_PASSWORD",
            "PGN_POSTGRES_PASSWORD",
            fallback="postgres",
        )
        return EnvironmentSettings(
            INSTALLER_PWD=installer_password,
            INSTALLER_USERID=installer_user,
            MYSQL_ROOT_PASSWORD=_first_non_empty("MYSQL_ROOT_PASSWORD", fallback=installer_password),
            MYSQL_ROOT_USER=_first_non_empty("MYSQL_ROOT_USER", fallback=installer_user),
            PGNSS_MYSQL_DATABASE=_first_non_empty(
                "PGNSS_MYSQL_DATABASE",
                "PGNSS_POSTGRES_DB",
                "PGN_POSTGRES_DB",
                fallback="pgnss_db",
            ),
            PGNSS_MYSQL_HOST=_first_non_empty(
                "PGNSS_MYSQL_HOST",
                "PGNSS_POSTGRES_HOST",
                "PGN_POSTGRES_HOST",
                fallback="127.0.0.1",
            ),
            PGNSS_MYSQL_TCP_PORT=_first_non_empty_int(
                "PGNSS_MYSQL_TCP_PORT",
                "PGNSS_POSTGRES_PORT",
                "PGN_POSTGRES_PORT",
                fallback=5432,
            ),
        )

    @property
    def INSTALLER_PWD(self) -> str:
        return self.env.INSTALLER_PWD

    @property
    def INSTALLER_USERID(self) -> str:
        return self.env.INSTALLER_USERID

    @property
    def MYSQL_ROOT_PASSWORD(self) -> str:
        return self.env.MYSQL_ROOT_PASSWORD

    @property
    def MYSQL_ROOT_USER(self) -> str:
        return self.env.MYSQL_ROOT_USER

    @property
    def PGNSS_MYSQL_DATABASE(self) -> str:
        return self.env.PGNSS_MYSQL_DATABASE

    @property
    def PGNSS_MYSQL_HOST(self) -> str:
        return self.env.PGNSS_MYSQL_HOST

    @property
    def PGNSS_MYSQL_TCP_PORT(self) -> int:
        return self.env.PGNSS_MYSQL_TCP_PORT

    @property
    def default_sqlite_database_url(self) -> str:
        return f"sqlite:///{(Path.cwd() / 'pgn_simulator.db').resolve()}"


settings = Settings()
