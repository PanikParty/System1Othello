from s1othello.engine import (
    Position, apply_move, coord_to_rc, disc_counts, has_any_legal_move,
    initial_board, legal_moves, rc_to_coord,
)


def test_initial_legal_moves():
    b = initial_board()
    assert sorted(legal_moves(b, "B")) == ["C4", "D3", "E6", "F5"]
    assert sorted(legal_moves(b, "W")) == ["C5", "D6", "E3", "F4"]


def test_coord_roundtrip():
    for r in range(8):
        for c in range(8):
            assert coord_to_rc(rc_to_coord(r, c)) == (r, c)


def test_apply_move_flips():
    b = initial_board()
    b2 = apply_move(b, "B", "D3")
    black, white = disc_counts(b2)
    assert black == 4 and white == 1  # D3 flips D4


def test_illegal_move_raises():
    b = initial_board()
    try:
        apply_move(b, "B", "A1")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_full_game_terminates():
    pos = Position.start()
    n = 0
    while not pos.is_terminal():
        moves = pos.legal()
        assert moves, "to_move with no legal_moves should not happen outside terminal"
        pos = pos.step(moves[0])
        n += 1
        assert n < 200, "game should always terminate well under 200 plies"
    b, w = disc_counts(pos.board)
    assert b + w <= 64
    assert not has_any_legal_move(pos.board, "B")
    assert not has_any_legal_move(pos.board, "W")
