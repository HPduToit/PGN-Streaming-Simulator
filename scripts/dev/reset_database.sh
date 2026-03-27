#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

source "$SCRIPT_DIR/source.sh"

echo "Resetting PGN simulator database and wiping generated output"
mkdir -p pgn_output
find pgn_output -mindepth 1 -maxdepth 1 -exec rm -rf {} +

docker compose up -d pgn_db

while true; do
    echo "Waiting for PostgreSQL to become healthy..."
    sleep 5
    health_status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' pgn_db 2>/dev/null || echo "missing")
    if [[ "$health_status" == "healthy" ]]; then
        break
    fi
done

poetry run python -m pgncs.main reset-db --yes --wipe-output
