from __future__ import annotations

import unittest
from textwrap import dedent

from pgncs.config import BaseSettings
from pgncs.timing import BoardMoveScheduler


class FakeGame:
    def __init__(
        self,
        board_index: int,
        *,
        move_count: int = 0,
        finished: bool = False,
    ) -> None:
        self.board_index = board_index
        self.move_count = move_count
        self.finished = finished

    def is_finished(self) -> bool:
        return self.finished


class TestBoardMoveScheduler(unittest.TestCase):
    def test_scheduler_tracks_due_times_per_board(self) -> None:
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
                """
            )
        )
        settings.validate()

        current_time = 100.0

        def now() -> float:
            return current_time

        games = [FakeGame(1), FakeGame(2)]
        scheduler = BoardMoveScheduler(settings, now=now)
        scheduler.reset(games)

        self.assertEqual([game.board_index for game in scheduler.due_games(games)], [1, 2])

        games[0].move_count = 1
        scheduler.schedule_after_turn(games[0])
        games[1].move_count = 1
        scheduler.schedule_after_turn(games[1])

        self.assertEqual(scheduler.seconds_until_next_due(games), 3.0)

        current_time = 102.0
        self.assertEqual(scheduler.due_games(games), [])
        self.assertEqual(scheduler.seconds_until_next_due(games), 1.0)

        current_time = 103.0
        self.assertEqual([game.board_index for game in scheduler.due_games(games)], [1])

        games[0].move_count = 5
        scheduler.schedule_after_turn(games[0])
        self.assertEqual(scheduler.seconds_until_next_due(games), 2.0)

        current_time = 105.0
        self.assertEqual([game.board_index for game in scheduler.due_games(games)], [1, 2])

    def test_finished_board_is_removed_from_schedule(self) -> None:
        settings = BaseSettings.from_yaml_text(
            dedent(
                """
                move_interval_seconds: 5
                number_of_boards: 1
                max_moves_per_game: 20
                """
            )
        )
        settings.validate()

        game = FakeGame(1, finished=True)
        scheduler = BoardMoveScheduler(settings, now=lambda: 100.0)
        scheduler.reset([game])

        scheduler.schedule_after_turn(game)

        self.assertEqual(scheduler.due_games([game]), [])
        self.assertEqual(scheduler.seconds_until_next_due([game]), 0.0)


if __name__ == "__main__":
    unittest.main()
