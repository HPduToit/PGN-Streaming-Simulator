"""Per-board move timing helpers."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from .config import BaseSettings

if TYPE_CHECKING:
    from .game import LiveGame


class BoardMoveScheduler:
    """Track when each board is due to make its next move."""

    def __init__(
        self,
        settings: BaseSettings,
        *,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.settings = settings
        self._now = now
        self._next_due_at: dict[int, float] = {}

    def reset(self, games: Iterable[LiveGame]) -> None:
        self._next_due_at = {game.board_index: 0.0 for game in games}

    def due_games(self, games: Iterable[LiveGame]) -> list[LiveGame]:
        now = self._current_time()
        return [
            game
            for game in games
            if not game.is_finished()
            and self._next_due_at.get(game.board_index, 0.0) <= now
        ]

    def schedule_after_turn(self, game: LiveGame) -> None:
        if game.is_finished():
            self._next_due_at.pop(game.board_index, None)
            return

        interval_seconds = self.settings.get_move_interval_seconds(
            game.board_index,
            game.move_count,
        )
        self._next_due_at[game.board_index] = self._current_time() + interval_seconds

    def seconds_until_next_due(self, games: Iterable[LiveGame]) -> float:
        active_due_times = [
            self._next_due_at.get(game.board_index, 0.0)
            for game in games
            if not game.is_finished()
        ]
        if not active_due_times:
            return 0.0
        return max(0.0, min(active_due_times) - self._current_time())

    def _current_time(self) -> float:
        if self._now is not None:
            return self._now()
        return time.monotonic()
