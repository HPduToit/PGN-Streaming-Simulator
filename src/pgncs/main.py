"""Main entry point for the chess tournament simulator.

This program simulates a live chess tournament by playing random legal moves
on multiple parallel boards and continuously updating PGN files.

Usage:
    pgncreationsimulator --config config.yaml

Or:
    python -m pgncreationsimulator --config config.yaml

The program will:
- Create PGN files for each board (board_1.pgn, board_2.pgn, etc.)
- Update these files after every move
- Optionally maintain a tournament.pgn file with all finished games
- Log moves and game results to stdout

Press Ctrl+C to stop the program gracefully.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from pgncs.config import BaseSettings
from pgncs.manager import GameManager
from pgncs.writer import PgnWriter


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Chess tournament simulator with live PGN updates"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to configuration file (YAML format)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        settings = BaseSettings.from_file(args.config)
        settings.validate()
        
        # Log configuration summary
        logger.info("Configuration loaded:")
        logger.info(f"  Boards: {settings.number_of_boards}")
        logger.info(f"  Move interval: {settings.move_interval_seconds}s")
        logger.info(f"  Max moves per game: {settings.max_moves_per_game}")
        logger.info(f"  Output directory: {settings.output_directory}")
        logger.info(f"  Event: {settings.event_name}")
        logger.info(f"  Auto-restart: {settings.auto_restart_games}")
        logger.info(f"  Tournament file: {settings.use_single_tournament_file}")
        
        # Ensure output directory exists
        output_dir = Path(settings.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory ready: {output_dir.absolute()}")
        
        # Initialize components
        writer = PgnWriter(settings.output_directory)
        manager = GameManager(settings, writer)
        
        # Setup signal handler for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("\nReceived interrupt signal, shutting down gracefully...")
            manager.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Main loop
        logger.info("Starting tournament simulation...")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                manager.make_moves()
                time.sleep(settings.move_interval_seconds)
        except KeyboardInterrupt:
            logger.info("\nReceived keyboard interrupt, shutting down...")
            manager.shutdown()
    
    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration validation error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

