#!/usr/bin/env python3
"""Reshuffle existing player names and PGN assignments in a simulator config."""

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


FIELDS = ("white_name", "black_name", "pgn_source_path")
MAX_ATTEMPTS = 10_000


def shuffled_names(names: list[str]) -> list[str]:
    if len(set(names)) != len(names):
        raise ValueError("Player names must be unique to create new pairings")

    old_pairs = {
        frozenset(names[index : index + 2]) for index in range(0, len(names), 2)
    }
    rng = random.SystemRandom()
    for _ in range(MAX_ATTEMPTS):
        result = names.copy()
        rng.shuffle(result)
        if all(
            not set(result[index : index + 2]) & set(names[index : index + 2])
            and frozenset(result[index : index + 2]) not in old_pairs
            for index in range(0, len(names), 2)
        ):
            return result
    raise ValueError("Could not find new board pairings for these players")


def shuffled_paths(paths: list[str]) -> list[str]:
    if max(Counter(paths).values()) * 2 > len(paths):
        raise ValueError("A PGN source is used on too many boards to change every board")

    rng = random.SystemRandom()
    for _ in range(MAX_ATTEMPTS):
        result = paths.copy()
        rng.shuffle(result)
        if all(new != old for new, old in zip(result, paths)):
            return result
    raise ValueError("Could not change the PGN source on every board")


def board_fields(text: str) -> list[dict[str, ScalarNode]]:
    root = yaml.compose(text)
    if not isinstance(root, MappingNode):
        raise ValueError("Expected a YAML mapping")
    boards = next(
        (value for key, value in root.value if key.value == "board_configs"), None
    )
    if not isinstance(boards, SequenceNode) or not boards.value:
        raise ValueError("Expected a non-empty board_configs list")

    result = []
    for board in boards.value:
        if not isinstance(board, MappingNode):
            raise ValueError("Each board config must be a mapping")
        fields = {key.value: value for key, value in board.value}
        if any(
            key not in fields
            or not isinstance(fields[key], ScalarNode)
            or fields[key].tag != "tag:yaml.org,2002:str"
            or not fields[key].value
            for key in FIELDS
        ):
            raise ValueError(
                "Each board needs white_name, black_name and pgn_source_path strings"
            )
        if (
            fields.get("move_strategy") is None
            or fields["move_strategy"].value != "pgn_file"
        ):
            raise ValueError("Each board must use move_strategy: pgn_file")
        result.append({key: fields[key] for key in FIELDS})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "config.yaml",
        help="YAML config to shuffle (default: project config.yaml)",
    )
    args = parser.parse_args()
    config = args.config.resolve()
    original = config.read_text(encoding="utf-8")
    boards = board_fields(original)
    names = [
        board[key].value for board in boards for key in ("white_name", "black_name")
    ]
    paths = [board["pgn_source_path"].value for board in boards]
    new_names = shuffled_names(names)
    new_paths = shuffled_paths(paths)

    replacements = []
    for index, board in enumerate(boards):
        for offset, key in enumerate(("white_name", "black_name")):
            node = board[key]
            replacements.append(
                (node.start_mark.index, node.end_mark.index, new_names[2 * index + offset])
            )
        node = board["pgn_source_path"]
        replacements.append((node.start_mark.index, node.end_mark.index, new_paths[index]))

    updated = original
    for start, end, value in sorted(replacements, reverse=True):
        updated = updated[:start] + json.dumps(value, ensure_ascii=False) + updated[end:]

    changed_boards = board_fields(updated)
    if Counter(names) != Counter(
        board[key].value
        for board in changed_boards
        for key in ("white_name", "black_name")
    ) or Counter(paths) != Counter(
        board["pgn_source_path"].value for board in changed_boards
    ):
        raise ValueError("Shuffled config did not preserve names and PGN counts")
    config.write_text(updated, encoding="utf-8")
    for index, board in enumerate(changed_boards, start=1):
        print(
            f"Board {index}: {board['white_name'].value} vs "
            f"{board['black_name'].value} — {board['pgn_source_path'].value}"
        )
    print(f"Updated {config}")


if __name__ == "__main__":
    main()
