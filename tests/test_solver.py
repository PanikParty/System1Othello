from conftest import random_position
from s1othello.engine import Position, empties, initial_board
from s1othello.solver import best_move, move_values


def test_best_move_is_legal_and_argmax():
    b = initial_board()
    move, values = best_move(b, "B", depth=4)
    assert set(values) == set(Position(b, "B").legal())
    assert values[move] == max(values.values())


def test_exact_switch_by_empties():
    pos = random_position(5, 12)
    e = empties(pos.board)
    assert move_values(pos.board, pos.to_move, depth=2, exact_empties=e)[1] is True
    assert move_values(pos.board, pos.to_move, depth=2, exact_empties=e - 1)[1] is False


def test_exact_values_are_disc_differentials():
    pos = random_position(9, 10)
    values, exact = move_values(pos.board, pos.to_move, exact_empties=10)
    assert exact and all(-64 <= v <= 64 for v in values.values())
