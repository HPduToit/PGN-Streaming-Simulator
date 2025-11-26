"""PGN file writer for chess tournament simulator.

Handles writing PGN strings to files with atomic writes to ensure
files are always in a valid, parseable state.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class PgnWriter:
    """Handles writing PGN strings to files."""
    
    def __init__(self, output_directory: str):
        """Initialize the PGN writer.
        
        Args:
            output_directory: Directory where PGN files are written
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.tournament_file = self.output_directory / "tournament.pgn"
        
        logger.debug(f"PgnWriter initialized with output directory: {self.output_directory}")
    
    def write_board_pgn(self, board_index: int, pgn_string: str) -> None:
        """Write the PGN for a specific board to disk.
        
        Uses atomic writes (write to temp file then rename) to ensure
        the PGN file is always in a valid state.
        
        Args:
            board_index: The board number (1-based)
            pgn_string: The PGN string to write
        """
        filename = self.output_directory / f"board_{board_index}.pgn"
        
        # Write atomically: write to temp file, then rename
        try:
            # Create a temporary file in the same directory
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=self.output_directory,
                delete=False,
                suffix='.pgn.tmp'
            ) as tmp_file:
                tmp_file.write(pgn_string)
                tmp_path = Path(tmp_file.name)
            
            # Atomic rename
            tmp_path.replace(filename)
            logger.debug(f"Wrote PGN for board {board_index} to {filename}")
            
        except Exception as e:
            logger.error(f"Error writing PGN for board {board_index}: {e}")
            # Clean up temp file if it exists
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            raise
    
    def append_tournament_pgn(self, pgn_string: str) -> None:
        """Append a finished game's PGN to the tournament file.
        
        Args:
            pgn_string: The complete PGN string of a finished game
        """
        try:
            # Append to tournament file
            with open(self.tournament_file, 'a', encoding='utf-8') as f:
                f.write(pgn_string)
                f.write("\n\n")  # Separate games with blank lines
            
            logger.debug(f"Appended game to tournament file: {self.tournament_file}")
            
        except Exception as e:
            logger.error(f"Error appending to tournament file: {e}")
            raise

