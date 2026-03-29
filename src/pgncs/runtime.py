"""Runtime supervisor for database-backed tournaments."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .game import LiveGame
from .livechess import build_game_payload
from .repository import StoredTournament, TournamentRepository
from .writer import PgnWriter


logger = logging.getLogger(__name__)


class TournamentRunner:
    """Run one stored tournament until all boards finish."""

    def __init__(self, tournament: StoredTournament, repository: TournamentRepository) -> None:
        self.tournament = tournament
        self.repository = repository
        self.settings = tournament.settings
        self.round_no = self.settings.round_number
        self.run_revision = tournament.run_revision
        self.task: asyncio.Task[None] | None = None
        self._writer = PgnWriter(self._output_directory)

    @property
    def code(self) -> str:
        return self.tournament.code

    @property
    def _output_directory(self) -> str:
        return str((Path(self.settings.output_directory) / self.tournament.code).resolve())

    def start(self) -> None:
        self.task = asyncio.create_task(self.run(), name=f"tournament-{self.code}")

    async def run(self) -> None:
        games = self._build_games()
        self._writer.reset_tournament_file()
        try:
            for game in games:
                self._persist_game(game)

            while True:
                active_games = [game for game in games if not game.is_finished()]
                if not active_games:
                    logger.info("Tournament %s finished", self.code)
                    self.repository.mark_tournament_finished(self.code)
                    return

                for game in active_games:
                    result = game.make_next_move()
                    if result.move is not None:
                        logger.info(
                            "Tournament %s round %s board %s move %s",
                            self.code,
                            self.round_no,
                            game.board_index,
                            game.get_last_move_san(),
                        )
                    self._persist_game(game)

                    if game.is_finished() and self.settings.use_single_tournament_file:
                        self._writer.append_tournament_pgn(game.to_pgn_string())

                await asyncio.sleep(self.settings.move_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Tournament %s cancelled", self.code)
            raise
        except Exception as exc:
            logger.exception("Tournament %s failed: %s", self.code, exc)
            self.repository.mark_tournament_failed(self.code, str(exc))

    def _build_games(self) -> list[LiveGame]:
        games: list[LiveGame] = []
        for board_index in range(1, self.settings.number_of_boards + 1):
            board_settings = self.settings.get_board_settings(board_index)
            games.append(
                LiveGame(
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
            )
        return games

    def _persist_game(self, game: LiveGame) -> None:
        payload = build_game_payload(self.code, self.round_no, game)
        pgn_text = game.to_pgn_string()
        self._writer.write_board_pgn(game.board_index, pgn_text)
        self.repository.upsert_game_snapshot(
            tournament_code=self.code,
            round_no=self.round_no,
            board_no=game.board_index,
            payload=payload,
            pgn_text=pgn_text,
            is_finished=game.is_finished(),
        )


class TournamentRuntimeManager:
    """Background supervisor for active tournaments."""

    def __init__(self, repository: TournamentRepository) -> None:
        self.repository = repository
        self.runners: dict[str, TournamentRunner] = {}
        self._supervisor_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        self._supervisor_task = asyncio.create_task(self._supervise(), name="pgn-supervisor")

    async def stop(self) -> None:
        self._shutdown.set()
        if self._supervisor_task is not None:
            self._supervisor_task.cancel()
            try:
                await self._supervisor_task
            except asyncio.CancelledError:
                pass

        for runner in list(self.runners.values()):
            if runner.task is not None:
                runner.task.cancel()
        for runner in list(self.runners.values()):
            if runner.task is not None:
                try:
                    await runner.task
                except asyncio.CancelledError:
                    pass
        self.runners.clear()

    async def _supervise(self) -> None:
        while not self._shutdown.is_set():
            self._collect_finished_runners()
            tournaments = {t.code: t for t in self.repository.list_tournaments()}

            for code, runner in list(self.runners.items()):
                tournament = tournaments.get(code)
                if tournament is None or tournament.status != "running":
                    await self._cancel_runner(code, "tournament stopped")
                    continue
                if tournament.run_revision != runner.run_revision:
                    await self._cancel_runner(code, "tournament restart requested")

            for tournament in tournaments.values():
                if tournament.status != "running":
                    continue
                if tournament.code in self.runners:
                    continue
                runner = TournamentRunner(tournament, self.repository)
                runner.start()
                self.runners[tournament.code] = runner
                logger.info(
                    "Started runtime for tournament %s revision %s",
                    tournament.code,
                    tournament.run_revision,
                )
            await asyncio.sleep(1.0)

    def _collect_finished_runners(self) -> None:
        completed_codes = [
            code
            for code, runner in self.runners.items()
            if runner.task is not None and runner.task.done()
        ]
        for code in completed_codes:
            runner = self.runners.pop(code)
            if runner.task is None:
                continue
            try:
                runner.task.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("Runner for %s ended with error: %s", code, exc)

    async def _cancel_runner(self, code: str, reason: str) -> None:
        runner = self.runners.pop(code, None)
        if runner is None or runner.task is None:
            return
        logger.info("Cancelling runner for %s: %s", code, reason)
        runner.task.cancel()
        try:
            await runner.task
        except asyncio.CancelledError:
            pass
