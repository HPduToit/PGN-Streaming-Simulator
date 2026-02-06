"""Move selection strategies for simulated games."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import random

import chess
import chess.pgn


@dataclass
class StrategyResult:
    """Result of a strategy move selection."""

    move: Optional[chess.Move]
    stop: bool = False
    stop_reason: Optional[str] = None


class MoveStrategy:
    """Base class for move selection strategies."""

    def select_move(
        self,
        board: chess.Board,
        move_count: int,
    ) -> StrategyResult:
        raise NotImplementedError


class RandomMoveStrategy(MoveStrategy):
    """Selects a random legal move."""

    def select_move(
        self,
        board: chess.Board,
        move_count: int,
    ) -> StrategyResult:
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return StrategyResult(move=None)
        return StrategyResult(move=random.choice(legal_moves))


class ThreefoldPreclaimStrategy(MoveStrategy):
    """Forces a threefold repetition, optionally stopping one ply before it."""

    _sequence_uci: List[str] = [
        "g1f3",
        "g8f6",
        "f3g1",
        "f6g8",
        "g1f3",
        "g8f6",
        "f3g1",
        "f6g8",
    ]

    def __init__(self, stop_preclaim: bool) -> None:
        self._index = 0
        self._stop_preclaim = stop_preclaim

    def select_move(
        self,
        board: chess.Board,
        move_count: int,
    ) -> StrategyResult:
        if self._index >= len(self._sequence_uci):
            return StrategyResult(
                move=None,
                stop=True,
                stop_reason="threefold repetition reached",
            )
        if self._stop_preclaim and self._index == len(self._sequence_uci) - 1:
            return StrategyResult(
                move=None,
                stop=True,
                stop_reason="threefold repetition imminent (pre-claim)",
            )
        move = chess.Move.from_uci(self._sequence_uci[self._index])
        if move not in board.legal_moves:
            return StrategyResult(
                move=None,
                stop=True,
                stop_reason="planned threefold sequence blocked by position",
            )
        self._index += 1
        if self._index >= len(self._sequence_uci):
            return StrategyResult(
                move=move,
                stop=True,
                stop_reason="threefold repetition reached",
            )
        return StrategyResult(move=move)


class PgnFileStrategy(MoveStrategy):
    """Replays moves from a PGN file."""

    def __init__(self, pgn_path: str, game_index: int) -> None:
        self._index = 0
        self._moves: List[chess.Move] = []
        self._load_moves(pgn_path, game_index)

    def _load_moves(self, pgn_path: str, game_index: int) -> None:
        path = Path(pgn_path)
        if not path.exists():
            raise ValueError(f"PGN file not found: {pgn_path}")

        with open(path, "r", encoding="utf-8") as pgn_file:
            game = None
            for _ in range(game_index):
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break

        if game is None:
            raise ValueError(
                f"PGN game index {game_index} not found in file: {pgn_path}"
            )

        self._moves = list(game.mainline_moves())

    def select_move(
        self,
        board: chess.Board,
        move_count: int,
    ) -> StrategyResult:
        if self._index >= len(self._moves):
            return StrategyResult(
                move=None,
                stop=True,
                stop_reason="PGN moves exhausted",
            )

        move = self._moves[self._index]
        if move not in board.legal_moves:
            return StrategyResult(
                move=None,
                stop=True,
                stop_reason="PGN move illegal for current position",
            )
        self._index += 1
        return StrategyResult(move=move)


def create_move_strategy(
    name: str,
    stop_preclaim: bool,
    pgn_source_path: Optional[str] = None,
    pgn_game_index: int = 1,
) -> MoveStrategy:
    """Factory for move strategies based on config."""
    if name == "random":
        return RandomMoveStrategy()
    if name == "threefold_preclaim":
        return ThreefoldPreclaimStrategy(stop_preclaim=stop_preclaim)
    if name == "pgn_file":
        if not pgn_source_path:
            raise ValueError("pgn_source_path is required for pgn_file strategy")
        return PgnFileStrategy(
            pgn_path=pgn_source_path,
            game_index=pgn_game_index,
        )
    raise ValueError(f"Unsupported move strategy: {name}")
