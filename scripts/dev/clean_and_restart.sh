#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

source "$SCRIPT_DIR/source.sh"

read -p "Are you sure you want to run this script? This will remove Docker volumes for PostgreSQL, wipe generated output, and restart the local PGN server prerequisites. Type 'yes' to continue: " confirmation

if [[ "$confirmation" != "yes" ]]; then
    echo "Operation cancelled by user."
    exit 1
fi

mkdir -p pgn_output
find pgn_output -mindepth 1 -maxdepth 1 -exec rm -rf {} +

docker compose down -v --remove-orphans
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

echo "PostgreSQL is ready in container: pgn_db"
echo "Start the local server with:"
echo "  ./scripts/dev/start_server.sh"
echo "Create/start tournaments locally with:"
echo "  ./scripts/dev/start.sh"
echo "  ./scripts/dev/start_tournament.sh <uuid>"
