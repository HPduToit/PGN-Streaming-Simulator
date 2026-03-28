"""HTTP server for serving stored tournaments in a LiveChess-compatible shape."""

from __future__ import annotations

import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import BaseSettings
from .database import Database
from .livechess import build_round_payload, build_tournament_payload
from .repository import TournamentRepository
from .runtime import TournamentRuntimeManager


logger = logging.getLogger(__name__)

_repository: TournamentRepository | None = None
_runtime_manager: TournamentRuntimeManager | None = None
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
PGN_INPUT_DIRECTORY = PROJECT_ROOT / "pgn_input"


class ConfigPayload(BaseModel):
    yaml_text: str
    start: bool = False


class TournamentControlResponse(BaseModel):
    code: str
    status: str


def _default_allowed_origins() -> list[str]:
    raw_origins = os.getenv(
        "PGN_WEB_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


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


def _raise_http_from_exception(exc: Exception, *, default_status_code: int = 400) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=default_status_code, detail=str(exc))
    raise exc


def _load_settings_from_yaml_text(yaml_text: str) -> BaseSettings:
    settings = BaseSettings.from_yaml_text(yaml_text, base_directory=PROJECT_ROOT)
    settings.validate()
    if settings.auto_restart_games:
        raise ValueError("auto_restart_games must be false for persisted tournaments")
    return settings


def _load_default_config_text() -> str:
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")

    return BaseSettings(
        move_interval_seconds=2.0,
        number_of_boards=4,
        max_moves_per_game=200,
    ).to_yaml()


def _list_pgn_input_files() -> list[str]:
    if not PGN_INPUT_DIRECTORY.exists():
        return []

    return sorted(
        str(path.relative_to(PROJECT_ROOT))
        for path in PGN_INPUT_DIRECTORY.iterdir()
        if path.is_file() and path.suffix.lower() == ".pgn"
    )


def _clear_same_round_run_state(repository: TournamentRepository, code: str) -> None:
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


def _snapshot_summary(code: str, round_no: int) -> dict[str, Any]:
    repository = _require_repository()
    snapshots = repository.list_game_snapshots(code, round_no)
    live_boards = sum(1 for snapshot in snapshots if bool(snapshot.payload.get("live", False)))
    finished_boards = sum(1 for snapshot in snapshots if snapshot.is_finished)
    last_updated = max((snapshot.updated_at for snapshot in snapshots), default=None)
    return {
        "board_count": len(snapshots),
        "live_boards": live_boards,
        "finished_boards": finished_boards,
        "last_updated_at": last_updated,
    }


def _serialize_tournament(code: str) -> dict[str, Any]:
    repository = _require_repository()
    tournament = _get_tournament_or_404(code)
    snapshot_summary = _snapshot_summary(code, tournament.settings.round_number)
    is_runtime_active = bool(_runtime_manager and code in _runtime_manager.runners)

    return {
        "code": tournament.code,
        "status": tournament.status,
        "created_at": tournament.created_at,
        "started_at": tournament.started_at,
        "finished_at": tournament.finished_at,
        "last_error": tournament.last_error,
        "run_revision": tournament.run_revision,
        "settings": tournament.settings.to_dict(),
        "config_yaml": tournament.settings.to_yaml(),
        "runtime_active": is_runtime_active,
        "snapshot_summary": snapshot_summary,
    }


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/api/management/config-template")
async def get_config_template():
    return {"yaml_text": _load_default_config_text()}


@app.get("/api/management/pgn-input-files")
async def get_pgn_input_files():
    return {"items": _list_pgn_input_files()}


@app.post("/api/management/config/validate")
async def validate_config(payload: ConfigPayload):
    try:
        settings = _load_settings_from_yaml_text(payload.yaml_text)
        return {
            "valid": True,
            "settings": settings.to_dict(),
            "normalized_yaml": settings.to_yaml(),
        }
    except Exception as exc:
        _raise_http_from_exception(exc)


@app.get("/api/management/tournaments")
async def list_managed_tournaments():
    repository = _require_repository()
    tournaments = repository.list_tournaments()
    return {"items": [_serialize_tournament(tournament.code) for tournament in tournaments]}


@app.get("/api/management/tournaments/{code}")
async def get_managed_tournament(code: str):
    return _serialize_tournament(code)


@app.post("/api/management/tournaments", response_model=TournamentControlResponse)
async def create_managed_tournament(payload: ConfigPayload):
    try:
        repository = _require_repository()
        settings = _load_settings_from_yaml_text(payload.yaml_text)
        code = repository.create_tournament(settings)
        if payload.start:
            repository.mark_tournament_running(code)
        tournament = repository.get_tournament(code)
        if tournament is None:
            raise HTTPException(status_code=500, detail="Tournament creation failed")
        return TournamentControlResponse(code=code, status=tournament.status)
    except Exception as exc:
        _raise_http_from_exception(exc)


@app.put("/api/management/tournaments/{code}", response_model=TournamentControlResponse)
async def update_managed_tournament(code: str, payload: ConfigPayload):
    try:
        repository = _require_repository()
        tournament = _get_tournament_or_404(code)
        if tournament.status == "running":
            raise HTTPException(status_code=409, detail="Stop the tournament before updating its config")

        settings = _load_settings_from_yaml_text(payload.yaml_text)
        repository.update_tournament(code, settings)
        if payload.start:
            _clear_same_round_run_state(repository, code)
            repository.mark_tournament_running(code)

        updated_tournament = _get_tournament_or_404(code)
        return TournamentControlResponse(code=code, status=updated_tournament.status)
    except Exception as exc:
        _raise_http_from_exception(exc, default_status_code=409)


@app.post("/api/management/tournaments/{code}/start", response_model=TournamentControlResponse)
async def start_managed_tournament(code: str):
    try:
        repository = _require_repository()
        _get_tournament_or_404(code)
        _clear_same_round_run_state(repository, code)
        repository.mark_tournament_running(code)
        updated_tournament = _get_tournament_or_404(code)
        return TournamentControlResponse(code=code, status=updated_tournament.status)
    except Exception as exc:
        _raise_http_from_exception(exc, default_status_code=409)


@app.post("/api/management/tournaments/{code}/stop", response_model=TournamentControlResponse)
async def stop_managed_tournament(code: str):
    try:
        repository = _require_repository()
        _get_tournament_or_404(code)
        repository.mark_tournament_stopped(code)
        updated_tournament = _get_tournament_or_404(code)
        return TournamentControlResponse(code=code, status=updated_tournament.status)
    except Exception as exc:
        _raise_http_from_exception(exc, default_status_code=409)


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
