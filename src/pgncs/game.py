"""Live game representation for a single chess board."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import chess
import chess.pgn
from typing import Optional as Optional

from .strategy import StrategyResult, create_move_strategy


@dataclass(frozen=True)
class MoveClockAnnotation:
    """LiveChess move annotation with remaining and elapsed seconds."""

    elapsed_seconds: int
    remaining_seconds: int
    san: str

    def to_livechess_move(self) -> str:
        """Return the DGT-style move string."""
        return f"{self.san} {self.remaining_seconds}+{self.elapsed_seconds}"


class LiveGame:
    """Represents a single live chess game on a board."""

    def __init__(
        self,
        board_index: int,
        game_index: int,
        event_name: str,
        site: str,
        round_prefix: str,
        max_moves: int,
        move_strategy: str,
        threefold_stop_preclaim: bool,
        pgn_source_path: Optional[str],
        pgn_game_index: int,
        initial_clock_seconds: int,
        clock_increment_seconds: int = 0,
        monotonic_clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], float] | None = None,
    ):
        """Initialize a new live game.

        Args:
            board_index: The board number (1-based)
            game_index: The game number on this board (1-based, increments
                when games restart)
            event_name: Event name for PGN header
            site: Site name for PGN header
            round_prefix: Prefix for round identification
            max_moves: Maximum number of half-moves before forced draw
        """
        self.board_index = board_index
        self.game_index = game_index
        self.max_moves = max_moves
        self.board = chess.Board()
        self.move_count = 0
        self.initial_clock_seconds = int(initial_clock_seconds)
        self.clock_increment_seconds = int(clock_increment_seconds)
        self.white_clock_seconds = self.initial_clock_seconds
        self.black_clock_seconds = self.initial_clock_seconds
        self.first_move_ms: Optional[int] = None
        self.move_clock_annotations: list[MoveClockAnnotation] = []
        self._monotonic_clock = monotonic_clock or time.monotonic
        self._wall_clock = wall_clock or time.time
        self._last_clock_update_at = self._monotonic_clock()
        self._forced_stop_reason: Optional[str] = None
        self.strategy = create_move_strategy(
            move_strategy,
            stop_preclaim=threefold_stop_preclaim,
            pgn_source_path=pgn_source_path,
            pgn_game_index=pgn_game_index,
        )

        # Create PGN game object
        self.pgn_game = chess.pgn.Game()
        self.pgn_game.headers["Event"] = event_name
        self.pgn_game.headers["Site"] = site
        self.pgn_game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
        self.pgn_game.headers["Round"] = f"{round_prefix} {board_index}"
        white_player_number = (board_index * 2) - 1
        black_player_number = board_index * 2
        self.pgn_game.headers["White"] = f"Player {white_player_number}"
        self.pgn_game.headers["Black"] = f"Player {black_player_number}"
        self.pgn_game.headers["Board"] = str(board_index)
        if game_index > 1:
            self.pgn_game.headers["GameID"] = str(game_index)
        self.pgn_game.headers["Result"] = "*"

        # PGN node for tracking moves
        self.pgn_node = self.pgn_game

    def make_next_move(self) -> StrategyResult:
        """Make the next move chosen by the configured strategy.

        Returns:
            StrategyResult describing the action taken
        """
        if self.is_finished():
            return StrategyResult(move=None)

        move_started_at = self._monotonic_clock()
        moving_white = self.board.turn == chess.WHITE
        result = self.strategy.select_move(
            self.board,
            self.move_count,
        )
        if result.move is None:
            if result.stop:
                self._forced_stop_reason = result.stop_reason or "strategy stop"
            return result

        san = self.board.san(result.move)
        self.board.push(result.move)
        self.move_count += 1
        self.pgn_node = self.pgn_node.add_variation(result.move)
        self._record_move_clock(
            san=san,
            moving_white=moving_white,
            move_started_at=move_started_at,
        )

        if result.stop:
            self._forced_stop_reason = result.stop_reason or "strategy stop"

        return result

    def is_finished(self) -> bool:
        """Check if the game is finished."""
        if self._forced_stop_reason:
            return True
        if self.move_count >= self.max_moves:
            return True
        return self.board.is_game_over()

    def get_clock_payload(self) -> dict[str, int | bool | None]:
        """Return the current top-level LiveChess clock object."""
        return {
            "white": self.white_clock_seconds,
            "black": self.black_clock_seconds,
            "run": self.board.turn == chess.WHITE if not self.is_finished() else None,
            "time": int(self._wall_clock() * 1000),
        }

    def get_livechess_moves(self) -> list[str]:
        """Return DGT-style move strings with clock suffixes."""
        return [
            annotation.to_livechess_move() for annotation in self.move_clock_annotations
        ]

    def get_result(self) -> str:
        """Get the result string for the finished game.

        Returns:
            Result string: "1-0", "0-1", "1/2-1/2", or "*" if not finished
        """
        if not self.is_finished():
            return "*"

        if self._forced_stop_reason:
            return "1/2-1/2"

        if self.move_count >= self.max_moves:
            return "1/2-1/2"

        if self.board.is_checkmate():
            if self.board.turn == chess.WHITE:
                return "0-1"  # Black wins
            else:
                return "1-0"  # White wins
        elif self.board.is_stalemate():
            return "1/2-1/2"
        elif self.board.is_insufficient_material():
            return "1/2-1/2"
        elif self.board.is_seventyfive_moves():
            return "1/2-1/2"
        elif self.board.is_fivefold_repetition():
            return "1/2-1/2"
        else:
            # Should not happen, but default to draw
            return "1/2-1/2"

    def get_termination_reason(self) -> str:
        """Get a human-readable reason for game termination."""
        if self._forced_stop_reason:
            return self._forced_stop_reason
        if self.move_count >= self.max_moves:
            return "max moves reached"
        if self.board.is_checkmate():
            return "checkmate"
        if self.board.is_stalemate():
            return "stalemate"
        if self.board.is_insufficient_material():
            return "insufficient material"
        if self.board.is_seventyfive_moves():
            return "75-move rule"
        if self.board.is_fivefold_repetition():
            return "fivefold repetition"
        return "unknown"

    def to_pgn_string(self) -> str:
        """Convert the current game state to a PGN string."""
        # Update result header
        result = self.get_result()
        self.pgn_game.headers["Result"] = result

        # Generate PGN string
        exporter = chess.pgn.StringExporter(
            headers=True, variations=False, comments=False
        )
        return str(self.pgn_game.accept(exporter))

    def get_last_move_san(self) -> Optional[str]:
        """Get the SAN notation of the last move made."""
        if self.move_count == 0:
            return None

        # Get the last move from the board
        if len(self.board.move_stack) > 0:
            last_move = self.board.move_stack[-1]
            # We need to temporarily pop to get SAN
            temp_board = self.board.copy()
            temp_board.pop()
            return temp_board.san(last_move)
        return None

    def _record_move_clock(
        self,
        *,
        san: str,
        moving_white: bool,
        move_started_at: float,
    ) -> None:
        elapsed_seconds = max(
            0, int(round(move_started_at - self._last_clock_update_at))
        )
        self._last_clock_update_at = move_started_at
        if self.first_move_ms is None:
            self.first_move_ms = int(self._wall_clock() * 1000)

        if moving_white:
            self.white_clock_seconds = (
                max(0, self.white_clock_seconds - elapsed_seconds)
                + self.clock_increment_seconds
            )
            remaining_seconds = self.white_clock_seconds
        else:
            self.black_clock_seconds = (
                max(0, self.black_clock_seconds - elapsed_seconds)
                + self.clock_increment_seconds
            )
            remaining_seconds = self.black_clock_seconds

        self.move_clock_annotations.append(
            MoveClockAnnotation(
                elapsed_seconds=elapsed_seconds,
                remaining_seconds=remaining_seconds,
                san=san,
            )
        )
