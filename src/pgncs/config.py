"""Configuration management for the chess tournament simulator."""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any as Any, Dict as Dict, Optional as Optional

import yaml


ALLOWED_MOVE_STRATEGIES: set[str] = {"random", "threefold_preclaim", "pgn_file"}


@dataclass
class MoveIntervalScheduleEntry:
    """One segment of a per-board move interval schedule."""

    interval_seconds: float
    moves: Optional[int] = None


@dataclass
class BoardOverrideSettings:
    """Per-board override settings from YAML."""

    board: int
    move_strategy: Optional[str] = None
    pgn_source_path: Optional[str] = None
    pgn_game_index: Optional[int] = None
    threefold_stop_preclaim: Optional[bool] = None
    move_interval_schedule: Optional[list[MoveIntervalScheduleEntry]] = None


@dataclass
class BoardRuntimeSettings:
    """Fully resolved per-board settings after fallback."""

    move_strategy: str
    pgn_source_path: Optional[str]
    pgn_game_index: int
    threefold_stop_preclaim: bool
    move_interval_schedule: Optional[list[MoveIntervalScheduleEntry]]


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

        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
        settings = cls._from_raw_data(raw_data, base_directory=path.parent)
        return settings

    @classmethod
    def from_yaml_text(
        cls,
        yaml_text: str,
        *,
        base_directory: Optional[Path] = None,
    ) -> "BaseSettings":
        """Load settings from YAML text."""
        raw_data = yaml.safe_load(yaml_text)
        return cls._from_raw_data(raw_data, base_directory=base_directory)

    @classmethod
    def _from_raw_data(
        cls,
        raw_data: Any,
        *,
        base_directory: Optional[Path],
    ) -> "BaseSettings":
        """Normalize raw config payload and build settings."""
        data = cls._normalize_raw_data(raw_data)
        settings = cls(**data)
        settings.resolve_paths(base_directory=base_directory)
        return settings

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseSettings":
        """Rehydrate settings from persisted data."""
        payload = cls._normalize_raw_data(data)
        settings = cls(**payload)
        settings.resolve_paths(base_directory=None)
        return settings

    @staticmethod
    def _normalize_raw_data(raw_data: Any) -> dict[str, Any]:
        """Normalize raw YAML/dict config data into constructor kwargs."""
        if raw_data is not None and not isinstance(raw_data, dict):
            raise ValueError("Config payload must be a mapping")
        data = dict(raw_data or {})

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
        data["board_configs"] = BaseSettings._parse_board_configs(raw_board_configs)
        return data

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
                    move_interval_schedule=BaseSettings._parse_move_interval_schedule(
                        item.get("move_interval_schedule"),
                        board_config_index=idx - 1,
                    ),
                )
            )
        return parsed

    @staticmethod
    def _parse_move_interval_schedule(
        raw_schedule: Any,
        *,
        board_config_index: int,
    ) -> Optional[list[MoveIntervalScheduleEntry]]:
        """Parse a board's optional move interval schedule."""
        if raw_schedule is None:
            return None
        if not isinstance(raw_schedule, list):
            raise ValueError(
                f"board_configs[{board_config_index}].move_interval_schedule must be a list"
            )
        if not raw_schedule:
            raise ValueError(
                f"board_configs[{board_config_index}].move_interval_schedule cannot be empty"
            )

        parsed: list[MoveIntervalScheduleEntry] = []
        for idx, item in enumerate(raw_schedule, start=1):
            schedule_index = idx - 1
            if not isinstance(item, dict):
                raise ValueError(
                    f"board_configs[{board_config_index}].move_interval_schedule"
                    f"[{schedule_index}] must be a mapping"
                )
            if "interval_seconds" not in item:
                raise ValueError(
                    f"board_configs[{board_config_index}].move_interval_schedule"
                    f"[{schedule_index}].interval_seconds is required"
                )

            interval_value = item["interval_seconds"]
            if isinstance(interval_value, bool):
                raise ValueError(
                    f"board_configs[{board_config_index}].move_interval_schedule"
                    f"[{schedule_index}].interval_seconds must be a number"
                )
            try:
                interval_seconds = float(interval_value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"board_configs[{board_config_index}].move_interval_schedule"
                    f"[{schedule_index}].interval_seconds must be a number"
                ) from None

            moves_value = item.get("moves")
            moves: Optional[int] = None
            if moves_value is not None:
                if isinstance(moves_value, bool) or (
                    isinstance(moves_value, float) and not moves_value.is_integer()
                ):
                    raise ValueError(
                        f"board_configs[{board_config_index}].move_interval_schedule"
                        f"[{schedule_index}].moves must be an integer"
                    )
                try:
                    moves = int(moves_value)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"board_configs[{board_config_index}].move_interval_schedule"
                        f"[{schedule_index}].moves must be an integer"
                    ) from None

            parsed.append(
                MoveIntervalScheduleEntry(
                    moves=moves,
                    interval_seconds=interval_seconds,
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
                    move_interval_schedule=None,
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
                move_interval_schedule=(
                    override.move_interval_schedule
                    if override and override.move_interval_schedule is not None
                    else None
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

    def get_move_interval_seconds(self, board_index: int, completed_moves: int) -> float:
        """Return the interval before a board's next move."""
        if completed_moves < 0:
            raise ValueError("completed_moves must be >= 0")

        board_settings = self.get_board_settings(board_index)
        schedule = board_settings.move_interval_schedule
        if not schedule:
            return self.move_interval_seconds

        next_move_number = completed_moves + 1
        covered_moves = 0
        for entry in schedule:
            if entry.moves is None:
                return entry.interval_seconds
            covered_moves += entry.moves
            if next_move_number <= covered_moves:
                return entry.interval_seconds

        return schedule[-1].interval_seconds

    def resolve_paths(self, base_directory: Optional[Path]) -> None:
        """Resolve relative PGN and output paths against the config file directory."""
        if self.pgn_source_path:
            self.pgn_source_path = self._resolve_optional_path(
                self.pgn_source_path,
                base_directory,
            )

        self.output_directory = str(
            self._resolve_path(Path(self.output_directory), base_directory)
        )

        for override in self.board_configs:
            if override.pgn_source_path:
                override.pgn_source_path = self._resolve_optional_path(
                    override.pgn_source_path,
                    base_directory,
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to plain data for persistence."""
        return {
            "move_interval_seconds": self.move_interval_seconds,
            "number_of_boards": self.number_of_boards,
            "max_moves_per_game": self.max_moves_per_game,
            "move_strategy": self.move_strategy,
            "threefold_stop_preclaim": self.threefold_stop_preclaim,
            "pgn_source_path": self.pgn_source_path,
            "pgn_game_index": self.pgn_game_index,
            "output_directory": self.output_directory,
            "event_name": self.event_name,
            "site": self.site,
            "round_number": self.round_number,
            "round_prefix": self.round_prefix,
            "auto_restart_games": self.auto_restart_games,
            "use_single_tournament_file": self.use_single_tournament_file,
            "board_configs": [
                {
                    "board": override.board,
                    "move_strategy": override.move_strategy,
                    "pgn_source_path": override.pgn_source_path,
                    "pgn_game_index": override.pgn_game_index,
                    "threefold_stop_preclaim": override.threefold_stop_preclaim,
                    "move_interval_schedule": (
                        [
                            {
                                "moves": entry.moves,
                                "interval_seconds": entry.interval_seconds,
                            }
                            for entry in override.move_interval_schedule
                        ]
                        if override.move_interval_schedule is not None
                        else None
                    ),
                }
                for override in self.board_configs
            ],
        }

    def to_yaml(self) -> str:
        """Serialize settings to YAML for the web editor and exports."""
        return yaml.safe_dump(
            self.to_dict(),
            sort_keys=False,
            allow_unicode=False,
        )

    @staticmethod
    def _resolve_optional_path(path_value: str, base_directory: Optional[Path]) -> str:
        return str(BaseSettings._resolve_path(Path(path_value), base_directory))

    @staticmethod
    def _resolve_path(path_value: Path, base_directory: Optional[Path]) -> Path:
        if base_directory is not None and not path_value.is_absolute():
            return (base_directory / path_value).resolve()
        return path_value.resolve() if path_value.is_absolute() else path_value

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
            self._validate_move_interval_schedule(cfg)

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

    @staticmethod
    def _validate_move_interval_schedule(cfg: BoardOverrideSettings) -> None:
        if cfg.move_interval_schedule is None:
            return

        last_index = len(cfg.move_interval_schedule) - 1
        for idx, entry in enumerate(cfg.move_interval_schedule):
            if not math.isfinite(entry.interval_seconds) or entry.interval_seconds <= 0:
                raise ValueError(
                    "move_interval_schedule interval_seconds must be > 0 "
                    f"in board_configs for board {cfg.board}"
                )
            if entry.moves is None:
                if idx != last_index:
                    raise ValueError(
                        "Only the final move_interval_schedule entry may omit moves "
                        f"in board_configs for board {cfg.board}"
                    )
                continue
            if entry.moves <= 0:
                raise ValueError(
                    "move_interval_schedule moves must be >= 1 "
                    f"in board_configs for board {cfg.board}"
                )
