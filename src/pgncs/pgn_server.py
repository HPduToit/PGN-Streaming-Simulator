"""HTTP server for serving stored tournaments in a LiveChess-compatible shape."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .database import Database
from .livechess import build_round_payload, build_tournament_payload
from .repository import TournamentRepository
from .runtime import TournamentRuntimeManager


logger = logging.getLogger(__name__)

_repository: TournamentRepository | None = None
_runtime_manager: TournamentRuntimeManager | None = None


def _etag_for_payload(payload: dict[str, Any]) -> str:
    return f'"{hash(str(payload))}"'


def _require_repository() -> TournamentRepository:
    if _repository is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    return _repository


def _get_tournament_or_404(code: str):
    repository = _require_repository()
    tournament = repository.get_tournament(code)
    if tournament is None:
        raise HTTPException(status_code=404, detail=f"Tournament {code} not found")
    return tournament


def _build_tournament_response(code: str) -> dict[str, Any]:
    repository = _require_repository()
    tournament = _get_tournament_or_404(code)
    snapshots = repository.list_game_snapshots(code, tournament.settings.round_number)
    payloads = [snapshot.payload for snapshot in snapshots]
    return build_tournament_payload(
        tournament_code=code,
        event_name=tournament.settings.event_name,
        round_no=tournament.settings.round_number,
        game_payloads=payloads,
    )


def _build_round_response(code: str, round_no: int) -> dict[str, Any]:
    repository = _require_repository()
    tournament = _get_tournament_or_404(code)
    if round_no != tournament.settings.round_number:
        raise HTTPException(
            status_code=404,
            detail=f"Round {round_no} not found (active round is {tournament.settings.round_number})",
        )
    snapshots = repository.list_game_snapshots(code, round_no)
    return build_round_payload([snapshot.payload for snapshot in snapshots])


def _build_game_response(code: str, round_no: int, board_no: int) -> dict[str, Any]:
    repository = _require_repository()
    tournament = _get_tournament_or_404(code)
    if round_no != tournament.settings.round_number:
        raise HTTPException(
            status_code=404,
            detail=f"Round {round_no} not found (active round is {tournament.settings.round_number})",
        )
    snapshot = repository.get_game_snapshot(code, round_no, board_no)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Board {board_no} not found")
    return snapshot.payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize repository and runtime supervision."""
    del app
    global _repository, _runtime_manager

    database = Database(os.getenv("PGN_DATABASE_URL"))
    _repository = TournamentRepository(database)
    _repository.init_db()

    _runtime_manager = TournamentRuntimeManager(_repository)
    await _runtime_manager.start()
    logger.info("PGN server started")
    yield
    if _runtime_manager is not None:
        await _runtime_manager.stop()
    logger.info("PGN server stopped")


app = FastAPI(
    title="PGN Simulator Server",
    description="Serves database-backed tournaments as LiveChess JSON",
    lifespan=lifespan,
)


@app.get("/get/{code}/tournament.json")
@app.get("/{code}/get/tournament.json")
async def get_tournament(code: str):
    payload = _build_tournament_response(code)
    response = JSONResponse(content=payload)
    response.headers["ETag"] = _etag_for_payload(payload)
    return response


@app.get("/get/{code}/round-{round_no}/index.json")
@app.get("/{code}/get/round-{round_no}/index.json")
async def get_round_index(code: str, round_no: int):
    payload = _build_round_response(code, round_no)
    response = JSONResponse(content=payload)
    response.headers["ETag"] = _etag_for_payload(payload)
    return response


@app.get("/get/{code}/round-{round_no}/game-{board_no}.json")
@app.get("/{code}/get/round-{round_no}/game-{board_no}.json")
async def get_game_json(code: str, round_no: int, board_no: int, poll: str | None = None):
    del poll
    payload = _build_game_response(code, round_no, board_no)
    response = JSONResponse(content=payload)
    response.headers["ETag"] = f'"{len(payload.get("moves", []))}"'
    return response


@app.get("/health")
async def health_check():
    active_codes = sorted(_runtime_manager.runners.keys()) if _runtime_manager else []
    return {
        "status": "ok",
        "database_ready": _repository is not None,
        "active_tournaments": active_codes,
    }


def main() -> None:
    """CLI entry point for the FastAPI server."""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    host = os.getenv("PGN_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("PGN_SERVER_PORT", "8006"))
    logger.info("Starting PGN server on %s:%s", host, port)
    logger.info(
        "Database URL: %s",
        os.getenv("PGN_DATABASE_URL", "sqlite:///./pgn_simulator.db"),
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

