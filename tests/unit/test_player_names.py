from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from pgncs.config import BaseSettings
from pgncs.livechess import build_game_payload, build_round_payload
from pgncs.manager import GameManager
from pgncs.writer import PgnWriter


class TestPlayerNames(unittest.TestCase):
    def test_names_are_per_board_and_survive_config_persistence(self) -> None:
        settings = BaseSettings.from_yaml_text(dedent("""
            move_interval_seconds: 2
            number_of_boards: 3
            max_moves_per_game: 10
            board_configs:
              - board: 1
                white_name: Alice Example
                black_name: Bob Example
              - board: 2
                white_name: Carol Example
                black_name: Dan Example
            """))
        settings.validate()
        settings = BaseSettings.from_dict(settings.to_dict())
        settings.validate()

        with TemporaryDirectory() as tmp_dir:
            manager = GameManager(settings, PgnWriter(tmp_dir))
            payloads = [
                build_game_payload("test", 1, game) for game in manager.games
            ]

            self.assertEqual(
                [(item["white"], item["black"]) for item in payloads],
                [
                    ("Alice Example", "Bob Example"),
                    ("Carol Example", "Dan Example"),
                    ("Player 5", "Player 6"),
                ],
            )
            self.assertEqual(
                build_round_payload(payloads)["pairings"][1]["white"]["name"],
                "Carol Example",
            )
            self.assertIn(
                '[White "Alice Example"]',
                (Path(tmp_dir) / "board_1.pgn").read_text(encoding="utf-8"),
            )
            manager._restart_game(1)
            self.assertEqual(
                manager.games[0].pgn_game.headers["White"], "Alice Example"
            )

    def test_empty_or_non_string_name_is_rejected(self) -> None:
        for value in ('" "', '""', '42'):
            with self.subTest(value=value):
                settings = BaseSettings.from_yaml_text(dedent(f"""
                    move_interval_seconds: 2
                    number_of_boards: 1
                    max_moves_per_game: 10
                    board_configs:
                      - board: 1
                        white_name: {value}
                    """))
                with self.assertRaisesRegex(
                    ValueError, "white_name must be a non-empty string"
                ):
                    settings.validate()
