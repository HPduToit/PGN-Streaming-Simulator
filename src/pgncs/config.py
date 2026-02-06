"""Configuration management for the chess tournament simulator."""

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BaseSettings:
    """Configuration settings for the chess tournament simulator."""

    move_interval_seconds: float
    number_of_boards: int
    max_moves_per_game: int
    move_strategy: str = "random"
    threefold_stop_preclaim: bool = True
    pgn_source_path: Optional[str] = None
    pgn_game_index: int = 1
    output_directory: str = "./pgn_output"
    event_name: str = "Test Live Tournament"
    site: str = "LiveChessCloud Simulator"
    round_prefix: str = "Round 1 Board"
    auto_restart_games: bool = False
    use_single_tournament_file: bool = True

    @classmethod
    def from_file(cls, config_path: str) -> "BaseSettings":
        """Load settings from a YAML configuration file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        data.setdefault("move_strategy", "random")
        data.setdefault("threefold_stop_preclaim", True)
        data.setdefault("pgn_source_path", None)
        data.setdefault("pgn_game_index", 1)
        return cls(**data)

    def validate(self) -> None:
        """Validate configuration values."""
        if self.move_interval_seconds <= 0:
            raise ValueError("move_interval_seconds must be > 0")
        if self.number_of_boards <= 0:
            raise ValueError("number_of_boards must be > 0")
        if self.max_moves_per_game <= 0:
            raise ValueError("max_moves_per_game must be > 0")
        if not self.output_directory:
            raise ValueError("output_directory cannot be empty")
        if not self.event_name:
            raise ValueError("event_name cannot be empty")
        if not self.site:
            raise ValueError("site cannot be empty")
        if self.pgn_game_index <= 0:
            raise ValueError("pgn_game_index must be >= 1")
        if self.move_strategy == "pgn_file":
            if not self.pgn_source_path:
                raise ValueError("pgn_source_path is required for pgn_file strategy")
            pgn_path = Path(self.pgn_source_path)
            if not pgn_path.exists():
                raise ValueError(f"pgn_source_path not found: {self.pgn_source_path}")
        if self.move_strategy not in {"random", "threefold_preclaim", "pgn_file"}:
            raise ValueError(
                "move_strategy must be 'random', 'threefold_preclaim', or 'pgn_file'"
            )
