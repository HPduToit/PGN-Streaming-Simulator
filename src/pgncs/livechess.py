"""Helpers for building LiveChess-compatible payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .game import LiveGame


def board_serial(tournament_code: str, board_index: int) -> str:
    """Generate a stable synthetic board serial."""
    compact_code = tournament_code.replace("-", "")[:8].upper()
    return f"SIM-{compact_code}-{board_index:03d}"


def build_game_payload(
    tournament_code: str,
    round_no: int,
    game: LiveGame,
) -> dict[str, Any]:
    """Serialize a game into the JSON shape expected by DMA."""
    moves = _game_moves_to_san(game)
    live = not game.is_finished()
    return {
        "live": live,
        "serialNr": board_serial(tournament_code, game.board_index),
        "clock": {
            "white": 360000 if live else 0,
            "black": 360000 if live else 0,
            "run": None,
            "time": int(datetime.now(timezone.utc).timestamp() * 1000),
        },
        "moves": moves,
        "result": game.get_result(),
        "finished": not live,
        "white": game.pgn_game.headers.get("White", ""),
        "black": game.pgn_game.headers.get("Black", ""),
        "round": str(round_no),
        "event": game.pgn_game.headers.get("Event", ""),
    }


def build_round_payload(game_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Build index.json content from stored game payloads."""
    pairings: list[dict[str, Any]] = []
    for payload in game_payloads:
        white_name = str(payload.get("white", ""))
        black_name = str(payload.get("black", ""))
        pairings.append(
            {
                "white": {"name": white_name, "lname": white_name},
                "black": {"name": black_name, "lname": black_name},
                "result": payload.get("result", "*"),
                "live": bool(payload.get("live", False)),
            }
        )
    return {"date": None, "pairings": pairings}


def build_tournament_payload(
    tournament_code: str,
    event_name: str,
    round_no: int,
    game_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build tournament.json content from stored game payloads."""
    rounds = [{"count": 0, "live": 0} for _ in range(round_no)]
    live_count = sum(1 for payload in game_payloads if bool(payload.get("live", False)))
    if rounds:
        rounds[round_no - 1] = {"count": len(game_payloads), "live": live_count}
    return {
        "id": tournament_code,
        "name": event_name,
        "rounds": rounds,
        "eboards": [str(payload.get("serialNr", "")) for payload in game_payloads],
    }


def _game_moves_to_san(game: LiveGame) -> list[str]:
    moves: list[str] = []
    board = game.pgn_game.board()
    for move in game.pgn_game.mainline_moves():
        moves.append(board.san(move))
        board.push(move)
    return moves

