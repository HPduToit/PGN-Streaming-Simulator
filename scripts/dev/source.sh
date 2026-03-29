#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
fi

resolved_pgnss_db="${PGNSS_MYSQL_DATABASE:-${PGNSS_POSTGRES_DB:-${PGN_POSTGRES_DB:-pgnss_db}}}"
resolved_pgnss_user="${INSTALLER_USERID:-${PGNSS_MYSQL_USER:-${PGNSS_POSTGRES_USER:-${PGN_POSTGRES_USER:-postgres}}}}"
resolved_pgnss_password="${INSTALLER_PWD:-${PGNSS_MYSQL_PASSWORD:-${PGNSS_POSTGRES_PASSWORD:-${PGN_POSTGRES_PASSWORD:-postgres}}}}"
resolved_pgnss_host="${PGNSS_MYSQL_HOST:-${PGNSS_POSTGRES_HOST:-${PGN_POSTGRES_HOST:-127.0.0.1}}}"
resolved_pgnss_port="${PGNSS_MYSQL_TCP_PORT:-${PGNSS_POSTGRES_PORT:-${PGN_POSTGRES_PORT:-5432}}}"

export PGNSS_MYSQL_DATABASE="$resolved_pgnss_db"
export PGNSS_MYSQL_HOST="$resolved_pgnss_host"
export PGNSS_MYSQL_TCP_PORT="$resolved_pgnss_port"
export INSTALLER_USERID="$resolved_pgnss_user"
export INSTALLER_PWD="$resolved_pgnss_password"
export MYSQL_ROOT_USER="${MYSQL_ROOT_USER:-$resolved_pgnss_user}"
export MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-$resolved_pgnss_password}"

export PGNSS_POSTGRES_DB="$resolved_pgnss_db"
export PGNSS_POSTGRES_USER="$resolved_pgnss_user"
export PGNSS_POSTGRES_PASSWORD="$resolved_pgnss_password"
export PGNSS_POSTGRES_PORT="$resolved_pgnss_port"
export PGN_POSTGRES_DB="$resolved_pgnss_db"
export PGN_POSTGRES_USER="$resolved_pgnss_user"
export PGN_POSTGRES_PASSWORD="$resolved_pgnss_password"
export PGN_POSTGRES_PORT="$resolved_pgnss_port"
export PGN_SERVER_PORT="${PGN_SERVER_PORT:-8006}"
export PGN_DATABASE_URL="postgresql://${INSTALLER_USERID}:${INSTALLER_PWD}@${PGNSS_MYSQL_HOST}:${PGNSS_MYSQL_TCP_PORT}/${PGNSS_MYSQL_DATABASE}"

case ":${PYTHONPATH:-}:" in
    *":$ROOT_DIR/src:"*) ;;
    *) export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}" ;;
esac
