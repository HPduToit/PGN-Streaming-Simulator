"""Move selection strategies for simulated games."""

from dataclasses import dataclass
from typing import Optional, List
import random

import chess


@dataclass
class StrategyResult:
    """Result of a strategy move selection."""

    move: Optional[chess.Move]
    stop: bool = False
    stop_reason: Optional[str] = None


class MoveStrategy:
    """Base class for move selection strategies."""

    def select_move(self, board: chess.Board, move_count: int) -> StrategyResult:
        raise NotImplementedError


class RandomMoveStrategy(MoveStrategy):
    """Selects a random legal move."""

    def select_move(self, board: chess.Board, move_count: int) -> StrategyResult:
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

    def select_move(self, board: chess.Board, move_count: int) -> StrategyResult:
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


def create_move_strategy(name: str, stop_preclaim: bool) -> MoveStrategy:
    """Factory for move strategies based on config."""
    if name == "random":
        return RandomMoveStrategy()
    if name == "threefold_preclaim":
        return ThreefoldPreclaimStrategy(stop_preclaim=stop_preclaim)
    raise ValueError(f"Unsupported move strategy: {name}")
