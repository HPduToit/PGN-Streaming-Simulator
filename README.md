# Chess Tournament Simulator

A Python-based chess tournament simulator that plays random legal moves on multiple parallel boards and continuously updates PGN files in real-time, similar to live chess tournament displays.

## Features

- Simulates multiple parallel chess games (configurable number of boards)
- Supports per-board move strategies (`random`, `threefold_preclaim`, `pgn_file`) with cascading fallback
- Makes random legal moves or replays a PGN game
- Continuously updates PGN files after each move
- Supports automatic game restart when games finish
- Optional tournament-wide PGN file for all finished games
- Configurable via YAML configuration file
- Graceful shutdown handling

## Installation

This project uses Poetry for dependency management. Make sure you have Poetry installed, then:

```bash
# Install dependencies
source \<venv\>/bin/activate
poetry install

# Or if using the virtual environment directly
```

## Usage

1. Create or edit a configuration file (see `config.yaml` for an example):

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
auto_restart_games: true
use_single_tournament_file: true
```

2. Run the simulator:

```bash
# Using Poetry
poetry run pgncreationsimulator --config config.yaml

# Or directly with Python
python -m pgncreationsimulator --config config.yaml

# With verbose logging
python -m pgncreationsimulator --config config.yaml --verbose
```

3. Watch the PGN files update in real-time in the output directory.

4. Press `Ctrl+C` to stop the simulator gracefully.

## Configuration

The configuration file supports the following options:

- `move_interval_seconds` (float): How often each board makes a move (in seconds)
- `number_of_boards` (int): Number of parallel games to simulate
- `max_moves_per_game` (int): Maximum half-moves before forced draw
- `move_strategy` (str): Move selection strategy (`random`, `threefold_preclaim`, or `pgn_file`)
- `threefold_stop_preclaim` (bool): In threefold mode, stop one ply before the claimable repetition
- `pgn_source_path` (str): Global default PGN path for `pgn_file`; board 1 starts from this value and later boards may inherit it via fallback unless overridden in `board_configs`
- `pgn_game_index` (int): Global default 1-based game index paired with `pgn_source_path` for `pgn_file`; also participates in board fallback
- `board_configs` (list): Optional per-board overrides (`board`, `move_strategy`, `pgn_source_path`, `pgn_game_index`, `threefold_stop_preclaim`)
- `board_configs` fallback: Missing values for board N inherit from resolved board N-1 values; board 1 inherits from global config
- `board_configs` validation: board numbers must be unique, within `1..number_of_boards`, and any board that resolves to `pgn_file` must resolve to an existing `pgn_source_path` (direct override or inherited fallback)
- `output_directory` (str): Directory where PGN files are written
- `event_name` (str): Event name for PGN headers
- `site` (str): Site name for PGN headers
- `round_number` (int): Active round to expose from server endpoints (`round-{round_number}`); `round_index` and `round` are also accepted aliases
- `round_prefix` (str): Prefix for round/board identification
- `auto_restart_games` (bool): Automatically start new games when one finishes
- `use_single_tournament_file` (bool): Maintain a tournament.pgn file with all finished games

Example fallback behavior:
- If board 1 is `random`, board 2 is `pgn_file`, and board 3 has no `move_strategy`, board 3 resolves to `pgn_file`.
- If board 2 and board 3 both omit `move_strategy`, both resolve to board 1's strategy.

### Per-board override resolution

Each `board_configs` entry overrides only the fields you set. Any missing field inherits from the previous resolved board:

1. Board 1 starts from global defaults (`move_strategy`, `pgn_source_path`, `pgn_game_index`, `threefold_stop_preclaim`).
2. Board N (N > 1) starts from board N-1 resolved values.
3. Values present in board N override that base.

Notes:
- If `board` is omitted in an entry, it defaults to that entry's 1-based list position.
- `pgn_source_path` is intentionally both a global default and a per-board override field; this allows concise configs while still supporting board-specific PGN files.
- Auto-restarted games keep the same resolved per-board settings as their board's initial game.

## Output Files

- `board_1.pgn`, `board_2.pgn`, etc.: Individual PGN files for each board, updated after every move
- `tournament.pgn`: (if enabled) Contains all finished games, appended as they complete

## Game Termination

Games end when:
- Checkmate occurs
- Stalemate occurs
- Insufficient material (draw)
- 75-move rule (draw)
- Fivefold repetition (draw)
- Maximum move count is reached (draw)

## PGN HTTP Server

The project includes an HTTP server that serves PGN files in LiveChess Cloud JSON format, allowing the `event_download_manager` to poll it as if it were a real LiveChess Cloud instance.

### Starting the Server

```bash
# Using Poetry
poetry run pgn-server

# Or directly with Python
python -m pgncs.pgn_server

# With custom configuration via environment variables
PGN_OUTPUT_DIRECTORY=./pgn_output PGN_CONFIG_PATH=./config.yaml PGN_SERVER_HOST=127.0.0.1 PGN_SERVER_PORT=8000 poetry run pgn-server
```

### Server Endpoints

The server provides endpoints matching the LiveChess Cloud API format:

- `GET /get/{code}/tournament.json` - Tournament information
- `GET /get/{code}/round-{round_no}/index.json` - Round pairings (served for configured `round_number` only)
- `GET /get/{code}/round-{round_no}/game-{board_no}.json?poll` - Game data in JSON format (served for configured `round_number` only)
- `GET /health` - Health check endpoint

The `{code}` parameter is ignored but kept for API compatibility.

### Configuration

The server can be configured via environment variables:

- `PGN_OUTPUT_DIRECTORY` - Directory to watch for PGN files (default: `./pgn_output`)
- `PGN_CONFIG_PATH` - YAML config path used to load `round_number` (optional)
- If `PGN_CONFIG_PATH` is not set, server checks `./config.yaml` and then `PGN-Streaming-Simulator/config.yaml`
- `PGN_ACTIVE_ROUND` - Optional explicit round override (takes precedence over YAML)
- `PGN_SERVER_HOST` - Server host (default: `127.0.0.1`)
- `PGN_SERVER_PORT` - Server port (default: `8000`)

### Usage with event_download_manager

1. Start the PGN simulator:
   ```bash
   poetry run pgncreationsimulator --config config.yaml
   ```

2. Start the PGN server:
   ```bash
   poetry run pgn-server
   ```

3. Configure `event_download_manager` to use `http://127.0.0.1:8000/get/{code}/...` as the source URL instead of `https://1.pool.livechesscloud.com/get/{code}/...`

The server automatically watches the PGN directory and serves updated game data in real-time.

## Project Structure

```
pgncreationsimulator/
├── src/
│   └── pgncs/
│       ├── __init__.py
│       ├── config.py          # BaseSettings configuration class
│       ├── game.py            # LiveGame class for individual games
│       ├── manager.py          # GameManager for orchestrating games
│       ├── writer.py           # PgnWriter for file operations
│       ├── pgn_server.py       # HTTP server for serving PGN as JSON
│       └── main.py             # Main entry point
├── config.yaml                 # Sample configuration file
├── pyproject.toml              # Poetry configuration
└── README.md                   # This file
```

## Integration with DMA and ES

**1. Event Service (EVS) - Database & Coordination**
- Tracks tournaments, games, and sources in a database
- Identifies what needs to be downloaded via get_pending_download_requests()
- Exposes API endpoint: GET /live_sources/downloads/pending
- Consumes Redis streams to process incoming game data
- Stores PGN files and runs arbiter analysis

**2. Download Manager App (DMA) - Polling & Fetching**
- Polls LiveChess Cloud endpoints for game data
- Fetches PGN files and publishes updates to Redis streams
- Two main components:
- PresenceService: Polls based on arbiter presence
- PendingDownloadService: Polls Event Service for backlog work

**Summary**
1. Event Service tracks what needs downloading (missing rounds/games)
2. Download Manager polls Event Service for pending work
3. Download Manager fetches data from LiveChess Cloud
4. Download Manager publishes updates to Redis streams
5. Event Service consumes streams and saves PGN files
6. Event Service runs arbiter analysis and updates the database
7. This decouples polling (EDM) from storage/processing (EVS) via Redis streams.

## Requirements

- Python 3.8+
- python-chess library
- PyYAML library
- FastAPI (for PGN server)
- uvicorn (for PGN server)
- watchfiles (for PGN server file watching)

## License

This project is provided as-is for educational and demonstration purposes.
