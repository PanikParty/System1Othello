import random

from conftest import random_position
from s1othello import native
from s1othello.engine import Position, apply_move, disc_counts, legal_moves


def _brute(pos: Position, me: str) -> int:
    if pos.is_terminal():
        b, w = disc_counts(pos.board)
        return (b - w) if me == "B" else (w - b)
    vals = [_brute(pos.step(m), me) for m in pos.legal()]
    return max(vals) if pos.to_move == me else min(vals)


def test_movegen_and_flips_match_python_engine():
    rng = random.Random(0)
    lib = native.lib()
    for _ in range(40):
        pos = Position.start()
        while not pos.is_terminal():
            for pl in "BW":
                assert sorted(native.moves(pos.board, pl)) == sorted(legal_moves(pos.board, pl))
            m = rng.choice(pos.legal())
            p, o = native.to_bitboards(pos.board, pos.to_move)
            r, c = int(m[1]) - 1, "ABCDEFGH".index(m[0])
            f = lib.ob_flips(p, o, r * 8 + c)
            after = native.to_bitboards(apply_move(pos.board, pos.to_move, m), pos.to_move)
            assert after == (p | f | (1 << (r * 8 + c)), o & ~f)
            pos = pos.step(m)


def test_exact_values_match_brute_force():
    for seed in range(12):
        pos = random_position(seed, 7)
        vals = native.move_values(pos.board, pos.to_move, 0, True)
        for m, v in vals.items():
            assert v == _brute(pos.step(m), pos.to_move), (seed, m)
        assert native.solve(pos.board, pos.to_move) == max(vals.values())


def test_midgame_search_prefers_a_winning_move():
    # Black to move; H1 wipes out every white disc, which ends the game at once.
    board = (".WWWWWWB",) + ("........",) * 7
    vals = native.move_values(board, "B", 4, False)
    assert vals == {"A1": 10000 + 8}
