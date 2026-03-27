#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
fi

export PGN_POSTGRES_DB="${PGNSS_POSTGRES_DB:-${PGN_POSTGRES_DB:-pgn_simulator}}"
export PGN_POSTGRES_USER="${PGNSS_POSTGRES_USER:-${PGN_POSTGRES_USER:-postgres}}"
export PGN_POSTGRES_PASSWORD="${PGNSS_POSTGRES_PASSWORD:-${PGN_POSTGRES_PASSWORD:-postgres}}"
export PGN_POSTGRES_PORT="${PGNSS_POSTGRES_PORT:-${PGN_POSTGRES_PORT:-5432}}"
export PGN_SERVER_PORT="${PGN_SERVER_PORT:-8006}"
export PGN_DATABASE_URL="postgresql://${PGN_POSTGRES_USER}:${PGN_POSTGRES_PASSWORD}@127.0.0.1:${PGN_POSTGRES_PORT}/${PGN_POSTGRES_DB}"

case ":${PYTHONPATH:-}:" in
    *":$ROOT_DIR/src:"*) ;;
    *) export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}" ;;
esac
