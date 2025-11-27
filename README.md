# Chess Tournament Simulator

A Python-based chess tournament simulator that plays random legal moves on multiple parallel boards and continuously updates PGN files in real-time, similar to live chess tournament displays.

## Features

- Simulates multiple parallel chess games (configurable number of boards)
- Makes random legal moves for both White and Black
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
output_directory: "./pgn_output"
event_name: "Test Live Tournament"
site: "LiveChessCloud Simulator"
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
- `output_directory` (str): Directory where PGN files are written
- `event_name` (str): Event name for PGN headers
- `site` (str): Site name for PGN headers
- `round_prefix` (str): Prefix for round/board identification
- `auto_restart_games` (bool): Automatically start new games when one finishes
- `use_single_tournament_file` (bool): Maintain a tournament.pgn file with all finished games

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

## Project Structure

```
pgncreationsimulator/
├── pgncreationsimulator/
│   ├── __init__.py
│   ├── config.py          # BaseSettings configuration class
│   ├── game.py            # LiveGame class for individual games
│   ├── manager.py          # GameManager for orchestrating games
│   ├── writer.py           # PgnWriter for file operations
│   └── main.py             # Main entry point
├── config.yaml             # Sample configuration file
├── pyproject.toml          # Poetry configuration
└── README.md               # This file
```

## Requirements

- Python 3.8+
- python-chess library
- PyYAML library

## License

This project is provided as-is for educational and demonstration purposes.

