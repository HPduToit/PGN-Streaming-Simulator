"""Configuration management for the chess tournament simulator."""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any as Any, Dict as Dict, Optional as Optional


ALLOWED_MOVE_STRATEGIES: set[str] = {"random", "threefold_preclaim", "pgn_file"}


@dataclass
class BoardOverrideSettings:
    """Per-board override settings from YAML."""

    board: int
    move_strategy: Optional[str] = None
    pgn_source_path: Optional[str] = None
    pgn_game_index: Optional[int] = None
    threefold_stop_preclaim: Optional[bool] = None


@dataclass
class BoardRuntimeSettings:
    """Fully resolved per-board settings after fallback."""

    move_strategy: str
    pgn_source_path: Optional[str]
    pgn_game_index: int
    threefold_stop_preclaim: bool


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
    round_number: int = 1
    round_prefix: str = "Round 1 Board"
    auto_restart_games: bool = False
    use_single_tournament_file: bool = True
    board_configs: list[BoardOverrideSettings] = field(default_factory=list)
    _resolved_board_settings: Dict[int, BoardRuntimeSettings] = field(
        init=False,
        repr=False,
        default_factory=dict,
    )

    @classmethod
    def from_file(cls, config_path: str) -> "BaseSettings":
        """Load settings from a YAML configuration file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}

        # Accept round aliases used in some configs.
        round_value = data.get("round_number", data.get("round_index", data.get("round")))
        if round_value is not None:
            data["round_number"] = round_value
        data.pop("round_index", None)
        data.pop("round", None)

        data.setdefault("move_strategy", "random")
        data.setdefault("threefold_stop_preclaim", True)
        data.setdefault("pgn_source_path", None)
        data.setdefault("pgn_game_index", 1)
        data.setdefault("round_number", 1)
        raw_board_configs = data.get("board_configs") or []
        data["board_configs"] = cls._parse_board_configs(raw_board_configs)
        return cls(**data)

    @staticmethod
    def _parse_board_configs(raw_board_configs: Any) -> list[BoardOverrideSettings]:
        """Parse board config overrides from YAML."""
        if not isinstance(raw_board_configs, list):
            raise ValueError("board_configs must be a list")

        parsed: list[BoardOverrideSettings] = []
        for idx, item in enumerate(raw_board_configs, start=1):
            if not isinstance(item, dict):
                raise ValueError("Each entry in board_configs must be a mapping")
            board_value = item.get("board", idx)
            try:
                board_no = int(board_value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"board_configs[{idx - 1}].board must be an integer"
                ) from None
            parsed.append(
                BoardOverrideSettings(
                    board=board_no,
                    move_strategy=item.get("move_strategy"),
                    pgn_source_path=item.get("pgn_source_path"),
                    pgn_game_index=item.get("pgn_game_index"),
                    threefold_stop_preclaim=item.get("threefold_stop_preclaim"),
                )
            )
        return parsed

    def _resolve_board_settings(self) -> Dict[int, BoardRuntimeSettings]:
        """Resolve effective board settings with cascading fallback."""
        overrides_by_board = {item.board: item for item in self.board_configs}
        resolved: Dict[int, BoardRuntimeSettings] = {}

        for board_index in range(1, self.number_of_boards + 1):
            base = (
                resolved[board_index - 1]
                if board_index > 1
                else BoardRuntimeSettings(
                    move_strategy=self.move_strategy,
                    pgn_source_path=self.pgn_source_path,
                    pgn_game_index=self.pgn_game_index,
                    threefold_stop_preclaim=self.threefold_stop_preclaim,
                )
            )
            override = overrides_by_board.get(board_index)
            resolved[board_index] = BoardRuntimeSettings(
                move_strategy=(
                    override.move_strategy
                    if override and override.move_strategy is not None
                    else base.move_strategy
                ),
                pgn_source_path=(
                    override.pgn_source_path
                    if override and override.pgn_source_path is not None
                    else base.pgn_source_path
                ),
                pgn_game_index=(
                    override.pgn_game_index
                    if override and override.pgn_game_index is not None
                    else base.pgn_game_index
                ),
                threefold_stop_preclaim=(
                    override.threefold_stop_preclaim
                    if override and override.threefold_stop_preclaim is not None
                    else base.threefold_stop_preclaim
                ),
            )
        return resolved

    def get_board_settings(self, board_index: int) -> BoardRuntimeSettings:
        """Get effective runtime settings for a board."""
        if board_index <= 0 or board_index > self.number_of_boards:
            raise ValueError(
                f"board_index must be between 1 and {self.number_of_boards}"
            )
        if not self._resolved_board_settings:
            self._resolved_board_settings = self._resolve_board_settings()
        return self._resolved_board_settings[board_index]

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
        if self.round_number <= 0:
            raise ValueError("round_number must be >= 1")
        if self.pgn_game_index <= 0:
            raise ValueError("pgn_game_index must be >= 1")
        if self.move_strategy not in ALLOWED_MOVE_STRATEGIES:
            raise ValueError(
                "move_strategy must be 'random', 'threefold_preclaim', or 'pgn_file'"
            )
        seen_boards: set[int] = set()
        for cfg in self.board_configs:
            if cfg.board <= 0:
                raise ValueError("board_configs board value must be >= 1")
            if cfg.board > self.number_of_boards:
                raise ValueError(
                    f"board_configs contains board {cfg.board}, "
                    f"but number_of_boards is {self.number_of_boards}"
                )
            if cfg.board in seen_boards:
                raise ValueError(
                    f"Duplicate board_configs entry for board {cfg.board}; "
                    "use one entry per board"
                )
            seen_boards.add(cfg.board)
            if (
                cfg.move_strategy is not None
                and cfg.move_strategy not in ALLOWED_MOVE_STRATEGIES
            ):
                raise ValueError(
                    f"Invalid move_strategy '{cfg.move_strategy}' in "
                    f"board_configs for board {cfg.board}"
                )
            if cfg.pgn_game_index is not None and cfg.pgn_game_index <= 0:
                raise ValueError(
                    f"pgn_game_index must be >= 1 in board_configs for board {cfg.board}"
                )

        self._resolved_board_settings = self._resolve_board_settings()
        for board_index, board_cfg in self._resolved_board_settings.items():
            if board_cfg.move_strategy not in ALLOWED_MOVE_STRATEGIES:
                raise ValueError(
                    f"Invalid resolved move_strategy '{board_cfg.move_strategy}' "
                    f"for board {board_index}"
                )
            if board_cfg.pgn_game_index <= 0:
                raise ValueError(
                    f"Resolved pgn_game_index must be >= 1 for board {board_index}"
                )
            if board_cfg.move_strategy == "pgn_file":
                if not board_cfg.pgn_source_path:
                    raise ValueError(
                        f"pgn_source_path is required for pgn_file strategy on board {board_index}"
                    )
                pgn_path = Path(board_cfg.pgn_source_path)
                if not pgn_path.exists():
                    raise ValueError(
                        f"pgn_source_path not found for board {board_index}: "
                        f"{board_cfg.pgn_source_path}"
                    )
