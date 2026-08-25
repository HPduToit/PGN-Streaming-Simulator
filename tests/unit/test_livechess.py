from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from pgncs.game import LiveGame
from pgncs.livechess import build_game_payload


def _write_two_move_pgn(path: Path) -> None:
    path.write_text(
        dedent("""
            [Event "Clock Test"]
            [Site "Simulator"]
            [Date "2026.08.25"]
            [Round "1"]
            [White "White"]
            [Black "Black"]
            [Result "*"]

            1. e4 e5 *
            """).strip(),
        encoding="utf-8",
    )


class TestLiveChessPayloadClock(unittest.TestCase):
    def test_payload_contains_dgt_style_move_times_and_live_clock(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            pgn_path = Path(tmp_dir) / "clock-test.pgn"
            _write_two_move_pgn(pgn_path)
            current_monotonic = 100.0
            current_wall = 1_716_507_000.0

            def monotonic_clock() -> float:
                return current_monotonic

            def wall_clock() -> float:
                return current_wall

            game = LiveGame(
                board_index=1,
                game_index=1,
                event_name="Clock Test",
                site="Simulator",
                round_prefix="Round",
                max_moves=20,
                move_strategy="pgn_file",
                threefold_stop_preclaim=True,
                pgn_source_path=str(pgn_path),
                pgn_game_index=1,
                initial_clock_seconds=5400,
                monotonic_clock=monotonic_clock,
                wall_clock=wall_clock,
            )

            initial_payload = build_game_payload("clock-test", 1, game)
            self.assertEqual(initial_payload["firstMove"], None)
            self.assertEqual(initial_payload["moves"], [])
            self.assertEqual(
                initial_payload["clock"],
                {
                    "white": 5400,
                    "black": 5400,
                    "run": True,
                    "time": 1_716_507_000_000,
                },
            )

            game.make_next_move()
            first_move_payload = build_game_payload("clock-test", 1, game)
            self.assertEqual(first_move_payload["firstMove"], 1_716_507_000_000)
            self.assertEqual(first_move_payload["moves"], ["e4 5400+0"])
            self.assertEqual(first_move_payload["clock"]["white"], 5400)
            self.assertEqual(first_move_payload["clock"]["black"], 5400)
            self.assertEqual(first_move_payload["clock"]["run"], False)

            current_monotonic = 105.0
            current_wall = 1_716_507_005.0
            game.make_next_move()
            second_move_payload = build_game_payload("clock-test", 1, game)
            self.assertEqual(second_move_payload["moves"], ["e4 5400+0", "e5 5395+5"])
            self.assertEqual(second_move_payload["clock"]["white"], 5400)
            self.assertEqual(second_move_payload["clock"]["black"], 5395)
            self.assertEqual(second_move_payload["clock"]["run"], True)
            self.assertEqual(second_move_payload["clock"]["time"], 1_716_507_005_000)

    def test_finished_payload_matches_dgt_null_clock_shape(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            pgn_path = Path(tmp_dir) / "finished-clock-test.pgn"
            _write_two_move_pgn(pgn_path)
            current_monotonic = 100.0
            current_wall = 1_716_507_000.0

            def monotonic_clock() -> float:
                return current_monotonic

            def wall_clock() -> float:
                return current_wall

            game = LiveGame(
                board_index=1,
                game_index=1,
                event_name="Clock Test",
                site="Simulator",
                round_prefix="Round",
                max_moves=2,
                move_strategy="pgn_file",
                threefold_stop_preclaim=True,
                pgn_source_path=str(pgn_path),
                pgn_game_index=1,
                initial_clock_seconds=60,
                monotonic_clock=monotonic_clock,
                wall_clock=wall_clock,
            )

            game.make_next_move()
            current_monotonic = 103.0
            current_wall = 1_716_507_003.0
            game.make_next_move()

            payload = build_game_payload("clock-test", 1, game)
            self.assertEqual(payload["live"], False)
            self.assertEqual(payload["clock"], None)
            self.assertEqual(payload["moves"], ["e4 60+0", "e5 57+3"])


if __name__ == "__main__":
    unittest.main()
