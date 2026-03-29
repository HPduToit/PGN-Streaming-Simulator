"""CLI entry points for simulator management and legacy local simulation."""

from __future__ import annotations

import argparse
import logging
import shutil
import signal
import sys
import time
from pathlib import Path

from pgncs.config import BaseSettings
from pgncs.database import Database
from pgncs.manager import GameManager
from pgncs.repository import TournamentRepository
from pgncs.writer import PgnWriter


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the management CLI parser."""
    parser = argparse.ArgumentParser(
        description="Create, start, inspect, and reset persisted PGN simulator tournaments"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL. Defaults to PGN_DATABASE_URL or local SQLite.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a new stored tournament from config")
    create_parser.add_argument("--config", required=True, help="Path to configuration file")
    create_parser.add_argument("--start", action="store_true", help="Immediately mark the new tournament as running")

    start_parser = subparsers.add_parser("start", help="Mark an existing tournament as running")
    start_parser.add_argument("code", help="Tournament UUID/code")

    stop_parser = subparsers.add_parser("stop", help="Stop a running tournament")
    stop_parser.add_argument("code", help="Tournament UUID/code")

    update_parser = subparsers.add_parser("update", help="Replace a stored tournament config")
    update_parser.add_argument("code", help="Tournament UUID/code")
    update_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to replacement configuration file (default: %(default)s)",
    )

    status_parser = subparsers.add_parser("status", help="Show persisted tournament status")
    status_parser.add_argument("code", help="Tournament UUID/code")

    reset_parser = subparsers.add_parser("reset-db", help="Drop and recreate the simulator database schema")
    reset_parser.add_argument("--yes", action="store_true", help="Confirm destructive reset")
    reset_parser.add_argument("--wipe-output", action="store_true", help="Also remove generated output files")

    simulate_parser = subparsers.add_parser("simulate", help="Legacy single-config simulator mode")
    simulate_parser.add_argument("--config", required=True, help="Path to configuration file")

    return parser


def legacy_main(argv: list[str]) -> None:
    """Run the original single-config simulator loop for backward compatibility."""
    parser = argparse.ArgumentParser(
        description="Chess tournament simulator with live PGN updates"
    )
    parser.add_argument("--config", required=True, help="Path to configuration file (YAML format)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args(argv)

    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    settings = BaseSettings.from_file(args.config)
    settings.validate()

    logger.info("Configuration loaded:")
    logger.info("  Boards: %s", settings.number_of_boards)
    logger.info("  Move interval: %ss", settings.move_interval_seconds)
    logger.info("  Max moves per game: %s", settings.max_moves_per_game)
    logger.info("  Output directory: %s", settings.output_directory)
    logger.info("  Event: %s", settings.event_name)
    logger.info("  Round number: %s", settings.round_number)
    logger.info("  Move strategy: %s", settings.move_strategy)
    if settings.board_configs:
        logger.info("  Board overrides: %s", len(settings.board_configs))

    output_dir = Path(settings.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    writer = PgnWriter(settings.output_directory)
    manager = GameManager(settings, writer)

    def signal_handler(sig, frame):
        del sig, frame
        logger.info("Received interrupt signal, shutting down gracefully...")
        manager.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting tournament simulation...")
    try:
        while True:
            manager.make_moves()
            time.sleep(settings.move_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        manager.shutdown()


def _wipe_generated_output(repository: TournamentRepository) -> None:
    """Remove generated tournament output directories and legacy PGN files."""
    candidate_dirs: set[Path] = set()
    for tournament in repository.list_tournaments():
        output_dir = Path(tournament.settings.output_directory)
        candidate_dirs.add(output_dir)
        candidate_dirs.add(output_dir / tournament.code)

    candidate_dirs.add((Path.cwd() / "pgn_output").resolve())

    for path in sorted(candidate_dirs):
        if path.is_dir():
            if path.name == "pgn_output" or len(path.name) == 36:
                shutil.rmtree(path, ignore_errors=True)
                continue
            for board_file in path.glob("board_*.pgn"):
                board_file.unlink(missing_ok=True)
            tournament_file = path / "tournament.pgn"
            tournament_file.unlink(missing_ok=True)


def _clear_same_round_run_state(repository: TournamentRepository, code: str) -> None:
    """Clear persisted state only when restarting the currently configured round."""
    tournament = repository.get_tournament(code)
    if tournament is None:
        raise KeyError(f"Tournament not found: {code}")

    current_round = tournament.settings.round_number
    snapshots = repository.list_game_snapshots(code, current_round)
    if not snapshots:
        return

    output_dir = (Path(tournament.settings.output_directory) / code).resolve()
    shutil.rmtree(output_dir, ignore_errors=True)
    repository.clear_game_snapshots(code, current_round)


def main() -> None:
    """Main entry point."""
    argv = sys.argv[1:]
    legacy_requested = "--config" in argv and not any(
        arg in {"create", "start", "stop", "update", "status", "reset-db", "simulate"} for arg in argv
    )
    if legacy_requested:
        legacy_main(argv)
        return

    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    repository = TournamentRepository(Database(args.database_url))
    repository.init_db()

    try:
        if args.command == "simulate":
            legacy_args = ["--config", args.config]
            if args.verbose:
                legacy_args.append("--verbose")
            legacy_main(legacy_args)
            return

        if args.command == "create":
            settings = BaseSettings.from_file(args.config)
            settings.validate()
            if settings.auto_restart_games:
                raise ValueError("auto_restart_games must be false for persisted tournaments")
            code = repository.create_tournament(settings)
            if args.start:
                repository.mark_tournament_running(code)
            print(code)
            return

        if args.command == "start":
            tournament = repository.get_tournament(args.code)
            if tournament is None:
                raise KeyError(f"Tournament not found: {args.code}")
            _clear_same_round_run_state(repository, args.code)
            repository.mark_tournament_running(args.code)
            print(args.code)
            return

        if args.command == "stop":
            tournament = repository.get_tournament(args.code)
            if tournament is None:
                raise KeyError(f"Tournament not found: {args.code}")
            repository.mark_tournament_stopped(args.code)
            print(args.code)
            return

        if args.command == "update":
            tournament = repository.get_tournament(args.code)
            if tournament is None:
                raise KeyError(f"Tournament not found: {args.code}")
            if tournament.status == "running":
                raise ValueError("Stop the tournament before updating its config")
            settings = BaseSettings.from_file(args.config)
            settings.validate()
            if settings.auto_restart_games:
                raise ValueError("auto_restart_games must be false for persisted tournaments")
            repository.update_tournament(args.code, settings)
            print(args.code)
            return

        if args.command == "status":
            tournament = repository.get_tournament(args.code)
            if tournament is None:
                raise KeyError(f"Tournament not found: {args.code}")
            snapshots = repository.list_game_snapshots(args.code, tournament.settings.round_number)
            print(
                f"code={tournament.code} status={tournament.status} round={tournament.settings.round_number} "
                f"boards={len(snapshots)} created_at={tournament.created_at}"
            )
            return

        if args.command == "reset-db":
            if not args.yes:
                raise ValueError("reset-db requires --yes")
            if args.wipe_output:
                _wipe_generated_output(repository)
            repository.reset_db()
            print("database reset complete")
            return
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
