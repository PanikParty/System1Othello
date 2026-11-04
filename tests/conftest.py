import random

import pytest

from s1othello.engine import Position, empties
from s1othello.state import PromptSet


@pytest.fixture
def ps() -> PromptSet:
    return PromptSet.load("v1")


def random_position(seed: int, max_empties: int) -> Position:
    """A non-terminal position from uniform random play with at most `max_empties` empties."""
    rng = random.Random(seed)
    while True:
        pos = Position.start()
        while not pos.is_terminal() and empties(pos.board) > max_empties:
            pos = pos.step(rng.choice(pos.legal()))
        if not pos.is_terminal():
            return pos
