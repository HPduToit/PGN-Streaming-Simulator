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
    output_directory: str
    event_name: str
    site: str
    round_prefix: str
    auto_restart_games: bool
    use_single_tournament_file: bool
    
    @classmethod
    def from_file(cls, config_path: str) -> "BaseSettings":
        """Load settings from a YAML configuration file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
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

