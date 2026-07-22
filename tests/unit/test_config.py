from __future__ import annotations

import unittest
from textwrap import dedent

from pgncs.config import BaseSettings


class TestMoveIntervalScheduleConfig(unittest.TestCase):
    def test_board_schedule_selects_interval_for_next_move(self) -> None:
        settings = BaseSettings.from_yaml_text(
            dedent(
                """
                move_interval_seconds: 5
                number_of_boards: 2
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule:
                      - moves: 5
                        interval_seconds: 3
                      - moves: 5
                        interval_seconds: 2
                      - interval_seconds: 1
                """
            )
        )
        settings.validate()

        self.assertEqual(settings.get_move_interval_seconds(1, 0), 3.0)
        self.assertEqual(settings.get_move_interval_seconds(1, 4), 3.0)
        self.assertEqual(settings.get_move_interval_seconds(1, 5), 2.0)
        self.assertEqual(settings.get_move_interval_seconds(1, 9), 2.0)
        self.assertEqual(settings.get_move_interval_seconds(1, 10), 1.0)
        self.assertEqual(settings.get_move_interval_seconds(2, 0), 5)

    def test_board_schedule_round_trips_through_dict(self) -> None:
        settings = BaseSettings.from_yaml_text(
            dedent(
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule:
                      - moves: 2
                        interval_seconds: 4
                      - moves: 2
                        interval_seconds: 3
                """
            )
        )
        settings.validate()

        rehydrated = BaseSettings.from_dict(settings.to_dict())
        rehydrated.validate()

        self.assertEqual(rehydrated.get_move_interval_seconds(1, 0), 4.0)
        self.assertEqual(rehydrated.get_move_interval_seconds(1, 2), 3.0)
        self.assertEqual(rehydrated.get_move_interval_seconds(1, 99), 3.0)

    def test_board_schedules_do_not_cascade_to_following_boards(self) -> None:
        settings = BaseSettings.from_yaml_text(
            dedent(
                """
                move_interval_seconds: 5
                number_of_boards: 2
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_strategy: threefold_preclaim
                    move_interval_schedule:
                      - moves: 5
                        interval_seconds: 3
                """
            )
        )
        settings.validate()

        self.assertIsNone(settings.get_board_settings(2).move_interval_schedule)
        self.assertEqual(settings.get_board_settings(2).move_strategy, "threefold_preclaim")
        self.assertEqual(settings.get_move_interval_seconds(2, 0), 5)

    def test_invalid_board_schedule_is_rejected(self) -> None:
        cases = [
            (
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule: []
                """,
                "cannot be empty",
            ),
            (
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule:
                      - moves: 0
                        interval_seconds: 3
                """,
                "moves must be >= 1",
            ),
            (
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule:
                      - moves: 5
                        interval_seconds: 0
                """,
                "interval_seconds must be > 0",
            ),
            (
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule:
                      - moves: 1.5
                        interval_seconds: 3
                """,
                "moves must be an integer",
            ),
            (
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule:
                      - moves: 5
                        interval_seconds: true
                """,
                "interval_seconds must be a number",
            ),
            (
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                board_configs:
                  - board: 1
                    move_interval_schedule:
                      - interval_seconds: 3
                      - moves: 5
                        interval_seconds: 2
                """,
                "Only the final",
            ),
        ]

        for yaml_text, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                with self.assertRaisesRegex(ValueError, expected_message):
                    settings = BaseSettings.from_yaml_text(dedent(yaml_text))
                    settings.validate()


if __name__ == "__main__":
    unittest.main()
