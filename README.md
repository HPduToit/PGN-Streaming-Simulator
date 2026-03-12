# Chess Tournament Simulator

A Python-based chess tournament simulator that stores tournament configs in a database, preserves per-board config overrides, runs multiple tournaments from one server process, and serves LiveChess/DGT-compatible HTTP endpoints per tournament code.

## Features

- Creates persisted tournaments from YAML config files and assigns each one a UUID code
- Preserves branch-specific per-board overrides via `board_configs`
- Preserves `round_number` and serves only the configured active round per tournament
- Starts a specific stored tournament on demand
- Stops a specific running tournament on demand
- Runs multiple tournaments concurrently from one FastAPI server process
- Serves `tournament.json`, `round-{n}/index.json`, and `game-{board}.json?poll` per tournament code
- Writes per-board PGN files under `output_directory/<uuid>/`
- Stops a tournament automatically when all boards finish
- Includes destructive clean/reset/restart scripts similar to UMS
- Supports PostgreSQL in production and SQLite as a local fallback

## Installation

```bash
poetry install
```

For PostgreSQL-backed usage:

When using the provided wrapper scripts, you can set the PostgreSQL connection pieces instead and let the scripts build `PGN_DATABASE_URL` automatically:

```env
PGNSS_POSTGRES_DB=pgnss_db
PGNSS_POSTGRES_USER=rtinstall
PGNSS_POSTGRES_PASSWORD=N0Pa55wrd
PGNSS_POSTGRES_PORT=50009
PGN_SERVER_PORT=8006
```

If `PGNSS_POSTGRES_*` are set in your shell or `.env`, [source.sh](/run/media/bob/Work/Coding_Projects/RTE/PGN-Streaming-Simulator/scripts/dev/source.sh) and [source.ps1](/run/media/bob/Work/Coding_Projects/RTE/PGN-Streaming-Simulator/scripts/dev/source.ps1) generate `PGN_DATABASE_URL` for you, so `PGN_DATABASE_URL` does not need to be set manually when you start the simulator through the provided scripts.

You can also directly set PGN_DATABASE_URL but this will create issues if the values aren't the same as in the docker compose file.

```bash
export PGN_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pgn_simulator
```

If `PGN_DATABASE_URL` is not set, the simulator uses a local SQLite database file.

## Config File

Example `config.yaml`:

```yaml
move_interval_seconds: 2.0
number_of_boards: 4
max_moves_per_game: 200
move_strategy: "random"
threefold_stop_preclaim: true
pgn_source_path: ""
pgn_game_index: 1
board_configs:
  - board: 1
    move_strategy: "random"
  - board: 2
    move_strategy: "pgn_file"
    pgn_source_path: "./pgn_input/5fold_rep.pgn"
  - board: 3
    move_strategy: "pgn_file"
    pgn_source_path: "./pgn_input/3fold_rep.pgn"
  - board: 4
    move_strategy: "threefold_preclaim"
output_directory: "./pgn_output"
event_name: "Test Live Tournament"
site: "LiveChessCloud Simulator"
round_number: 1
round_prefix: "Round 1 Board"
auto_restart_games: false
use_single_tournament_file: true
```

For persisted tournaments, `auto_restart_games` must remain `false`.

## Docker Workflow

Docker is used only for PostgreSQL. The simulator service itself runs on the host machine and connects to the DB container through `PGN_DATABASE_URL`.

1. Copy `.env.example` to `.env` if you want custom ports or credentials.

2. Start the PostgreSQL container:

```bash
docker compose up -d pgn_db
```

Or use the destructive reset/restart flow:

```bash
./scripts/dev/clean_and_restart.sh
```

3. Start the simulator service locally:

```bash
./scripts/dev/start_server.sh
```

4. Create and start tournaments locally:

```bash
./scripts/dev/start.sh
./scripts/dev/start_tournament.sh <uuid>
./scripts/dev/stop_tournament.sh <uuid>
./scripts/dev/update_tournament.sh <uuid>
./scripts/dev/update_tournament.sh <uuid> config.yaml
poetry run pgn-tournament status <uuid>
```

All of those scripts source [source.sh](/run/media/bob/Work/Coding_Projects/RTE/PGN-Streaming-Simulator/scripts/dev/source.sh) or [source.ps1](/run/media/bob/Work/Coding_Projects/RTE/PGN-Streaming-Simulator/scripts/dev/source.ps1), which now read `.env` plus existing `PGN_POSTGRES_*` or `PGNSS_POSTGRES_*` variables so they point at the Dockerized PostgreSQL instance automatically.

## Local Workflow

1. Start the PostgreSQL container:

```bash
docker compose up -d pgn_db
```

2. Start the server:

```bash
./scripts/dev/start_server.sh
```

3. Create a stored tournament from a config file. This prints the generated UUID:

```bash
./scripts/dev/start.sh
```

Or directly:

```bash
source ./scripts/dev/source.sh
poetry run pgn-tournament create --config config.yaml --start
```

4. Start a specific existing tournament:

```bash
./scripts/dev/start_tournament.sh <uuid>
```

Calling `start` for an existing UUID resets that tournament’s stored board state and generated output for that code, then starts all games again from move one.

5. Stop a running tournament:

```bash
./scripts/dev/stop_tournament.sh <uuid>
```

6. Update the stored config for an existing stopped tournament:

```bash
./scripts/dev/update_tournament.sh <uuid>
./scripts/dev/update_tournament.sh <uuid> config-round-2.yaml
```

Without a second argument, `update_tournament.sh` uses the project `config.yaml`. This replaces the stored YAML-derived config for that UUID, preserves previously stored games from other rounds, and leaves it ready to start again.

7. Poll the tournament:

```bash
curl http://127.0.0.1:8006/get/<uuid>/tournament.json
curl http://127.0.0.1:8006/get/<uuid>/round-1/index.json
curl "http://127.0.0.1:8006/get/<uuid>/round-1/game-1.json?poll"
```

The server also accepts `/<uuid>/get/...` as an alias.

## Legacy Single-Config Mode

The old direct simulator mode still works:

```bash
poetry run pgncreationsimulator --config config.yaml
```

Or explicitly:

```bash
poetry run pgncreationsimulator simulate --config config.yaml
```

## Reset And Restart Scripts

Destructive reset of the Dockerized PostgreSQL plus local runtime prerequisites:

```bash
./scripts/dev/clean_and_restart.sh
```

Windows:

```powershell
.\scripts\dev\clean_and_restart.ps1
```

Database and generated output reset only:

```bash
./scripts/dev/reset_database.sh
```

These scripts:

- prompt for explicit confirmation
- wipe generated output under `pgn_output`
- run `docker compose down -v`
- restart the PostgreSQL container
- wait for PostgreSQL to become healthy
- run the local reset command against that Dockerized database

`scripts/dev/reset_database.sh` and `scripts/dev/reset_database.ps1` reset the running Dockerized database and wipe generated output without tearing the full stack down.

## Configuration Notes

- `board_configs` entries override only the fields you set
- missing values for board `N` fall back to resolved values from board `N-1`
- board `1` falls back to the global config
- `round_number` is persisted per tournament and controls which `round-{n}` routes are live
- `start <uuid>` clears persisted game state only when that UUID is being restarted for the same active round
- `stop <uuid>` marks that tournament as stopped and the host server cancels the active runner on its next supervisor pass
- `update <uuid> --config ...` requires the tournament to be stopped first, replaces the stored config, preserves previously stored games from other rounds, and resets the tournament to `created`

## HTTP Endpoints

- `GET /get/{code}/tournament.json`
- `GET /get/{code}/round-{round_no}/index.json`
- `GET /get/{code}/round-{round_no}/game-{board_no}.json?poll`
- `GET /{code}/get/tournament.json`
- `GET /{code}/get/round-{round_no}/index.json`
- `GET /{code}/get/round-{round_no}/game-{board_no}.json?poll`
- `GET /health`

The `{code}` path segment is now meaningful and routes to the stored tournament with that UUID.

## Database Model

The simulator stores:

- `tournaments`: tournament code, YAML-derived config, lifecycle status, timestamps, and error state
- `tournament_games`: per-board JSON payload snapshots plus the latest PGN text

When a tournament row is marked `running`, the server detects it and starts the simulator for that specific tournament.

## Output Files

For each running tournament, the simulator writes:

- `output_directory/<uuid>/board_1.pgn`, `board_2.pgn`, ...
- `output_directory/<uuid>/tournament.pgn` when `use_single_tournament_file` is enabled
- host `pgn_output/` files generated by the locally running `pgn-server`

## Integration with DMA and ES

The server is shaped for the downloader stack in this repo:

- `download_manager_app` can poll `.../get/{code}/tournament.json`
- `download_manager_app` can poll `.../get/{code}/round-{round_number}/index.json`
- `download_manager_app` can poll `.../get/{code}/round-{round_number}/game-{board}.json?poll`

## Project Structure

```text
PGN-Streaming-Simulator/
├── src/
│   └── pgncs/
│       ├── config.py
│       ├── database.py
│       ├── game.py
│       ├── livechess.py
│       ├── manager.py
│       ├── repository.py
│       ├── runtime.py
│       ├── writer.py
│       ├── pgn_server.py
│       └── main.py
├── config.yaml
├── docker-compose.yaml
├── scripts/
│   └── dev/
│       ├── source.sh
│       ├── source.ps1
│       ├── start.sh
│       ├── start.ps1
│       ├── start_server.sh
│       ├── start_server.ps1
│       ├── start_tournament.sh
│       ├── start_tournament.ps1
│       ├── stop_tournament.sh
│       ├── stop_tournament.ps1
│       ├── update_tournament.sh
│       ├── update_tournament.ps1
│       ├── reset_database.sh
│       ├── reset_database.ps1
│       ├── clean_and_restart.sh
│       └── clean_and_restart.ps1
├── pyproject.toml
└── README.md
```
