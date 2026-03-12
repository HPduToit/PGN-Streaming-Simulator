#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

source "$SCRIPT_DIR/source.sh"
CONFIG_PATH="${2:-config.yaml}"
poetry run pgn-tournament update "$1" --config "$CONFIG_PATH"
