"""Live game representation for a single chess board."""

import random
import chess
import chess.pgn
from datetime import datetime
from typing import Optional


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
    ):
        """Initialize a new live game.
        
        Args:
            board_index: The board number (1-based)
            game_index: The game number on this board (1-based, increments when games restart)
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
        
        # Create PGN game object
        self.pgn_game = chess.pgn.Game()
        self.pgn_game.headers["Event"] = event_name
        self.pgn_game.headers["Site"] = site
        self.pgn_game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
        self.pgn_game.headers["Round"] = f"{round_prefix} {board_index}"
        self.pgn_game.headers["White"] = f"Player {board_index} White"
        self.pgn_game.headers["Black"] = f"Player {board_index} Black"
        self.pgn_game.headers["Board"] = str(board_index)
        if game_index > 1:
            self.pgn_game.headers["GameID"] = str(game_index)
        self.pgn_game.headers["Result"] = "*"
        
        # PGN node for tracking moves
        self.pgn_node = self.pgn_game
    
    def make_random_move(self) -> Optional[chess.Move]:
        """Make a random legal move if the game is not finished.
        
        Returns:
            The move that was made, or None if the game is finished
        """
        if self.is_finished():
            return None
        
        # Get all legal moves
        legal_moves = list(self.board.legal_moves)
        if not legal_moves:
            return None
        
        # Choose a random move
        move = random.choice(legal_moves)
        
        # Apply the move
        self.board.push(move)
        self.move_count += 1
        
        # Add move to PGN
        self.pgn_node = self.pgn_node.add_variation(move)
        
        return move
    
    def is_finished(self) -> bool:
        """Check if the game is finished."""
        if self.move_count >= self.max_moves:
            return True
        return self.board.is_game_over()
    
    def get_result(self) -> str:
        """Get the result string for the finished game.
        
        Returns:
            Result string: "1-0", "0-1", "1/2-1/2", or "*" if not finished
        """
        if not self.is_finished():
            return "*"
        
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
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
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

