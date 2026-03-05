"""Game manager for orchestrating multiple parallel chess games."""

import logging
from typing import List as List

from .config import BaseSettings
from .game import LiveGame
from .writer import PgnWriter


logger = logging.getLogger(__name__)


class GameManager:
    """Manages multiple parallel chess games."""

    def __init__(self, settings: BaseSettings, writer: PgnWriter):
        """Initialize the game manager.

        Args:
            settings: Configuration settings
            writer: PGN writer instance
        """
        self.settings = settings
        self.writer = writer
        self.games: List[LiveGame] = []
        self._board_settings = {
            board_index: self.settings.get_board_settings(board_index)
            for board_index in range(1, self.settings.number_of_boards + 1)
        }
        self._initialize_games()

    def _initialize_games(self) -> None:
        """Initialize all game instances."""
        self.games = []
        for board_index in range(1, self.settings.number_of_boards + 1):
            board_settings = self._board_settings[board_index]
            game = LiveGame(
                board_index=board_index,
                game_index=1,
                event_name=self.settings.event_name,
                site=self.settings.site,
                round_prefix=self.settings.round_prefix,
                max_moves=self.settings.max_moves_per_game,
                move_strategy=board_settings.move_strategy,
                threefold_stop_preclaim=board_settings.threefold_stop_preclaim,
                pgn_source_path=board_settings.pgn_source_path,
                pgn_game_index=board_settings.pgn_game_index,
            )
            self.games.append(game)
            # Write initial PGN (empty game)
            self._write_game_pgn(game)

        logger.info(f"Initialized {len(self.games)} game boards")

    def _write_game_pgn(self, game: LiveGame) -> None:
        """Write the PGN for a specific game to disk."""
        pgn_string = game.to_pgn_string()
        self.writer.write_board_pgn(game.board_index, pgn_string)

    def _restart_game(self, board_index: int) -> None:
        """Restart a game on a specific board.

        Args:
            board_index: The board to restart (1-based)
        """
        # Find the current game on this board
        game = self.games[board_index - 1]
        new_game_index = game.game_index + 1
        board_settings = self._board_settings[board_index]

        # Create new game
        new_game = LiveGame(
            board_index=board_index,
            game_index=new_game_index,
            event_name=self.settings.event_name,
            site=self.settings.site,
            round_prefix=self.settings.round_prefix,
            max_moves=self.settings.max_moves_per_game,
            move_strategy=board_settings.move_strategy,
            threefold_stop_preclaim=board_settings.threefold_stop_preclaim,
            pgn_source_path=board_settings.pgn_source_path,
            pgn_game_index=board_settings.pgn_game_index,
        )
        self.games[board_index - 1] = new_game

        # Write initial PGN
        self._write_game_pgn(new_game)

        logger.info(f"Board {board_index}: Started new game #{new_game_index}")

    def make_moves(self) -> None:
        """Make one move for each active game."""
        for game in self.games:
            if not game.is_finished():
                result = game.make_next_move()
                if result.move:
                    # Get move in SAN notation for logging
                    move_san = game.get_last_move_san()
                    # Calculate move number (full moves, not half-moves)
                    # move_count is incremented after the move, so:
                    # move_count 1 = white's first move (full move 1)
                    # move_count 2 = black's first move (full move 1)
                    # move_count 3 = white's second move (full move 2)
                    full_move_num = (game.move_count + 1) // 2
                    # Determine if it's a white or black move
                    # Odd move_count = white move, even move_count = black move
                    is_white_move = game.move_count % 2 == 1
                    if is_white_move:
                        logger.info(
                            f"Board {game.board_index}: {full_move_num}. {move_san}"
                        )
                    else:
                        logger.info(
                            f"Board {game.board_index}: "
                            f"{full_move_num}... {move_san}"
                        )

                    # Update PGN file
                    self._write_game_pgn(game)

                # Check if game finished after this move or strategy stop
                if game.is_finished():
                    result_string = game.get_result()
                    reason = game.get_termination_reason()
                    logger.info(
                        f"Board {game.board_index}: Game finished - "
                        f"result {result_string} ({reason})"
                    )

                    # Final PGN write with result
                    self._write_game_pgn(game)

                    # Append to tournament file if enabled
                    if self.settings.use_single_tournament_file:
                        pgn_string = game.to_pgn_string()
                        self.writer.append_tournament_pgn(pgn_string)

                    # Restart game if auto-restart is enabled
                    if self.settings.auto_restart_games:
                        self._restart_game(game.board_index)

    def shutdown(self) -> None:
        """Gracefully shutdown, ensuring all PGN files are written."""
        logger.info("Shutting down, writing final PGN states...")
        for game in self.games:
            self._write_game_pgn(game)
        logger.info("Shutdown complete")
