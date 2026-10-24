from s1othello.engine import Position, initial_board
from s1othello.solver import best_move


def test_best_move_is_legal():
    b = initial_board()
    move, values = best_move(b, "B", depth=4)
    assert move in Position(b, "B").legal()
    assert set(values) == set(Position(b, "B").legal())


def test_exact_endgame_consistent_direction():
    # In the near-exact regime, the solver's reported value for the chosen
    # move must be >= every other move's value (it is the argmax by definition).
    b = initial_board()
    move, values = best_move(b, "B", depth=4)
    assert values[move] == max(values.values())
