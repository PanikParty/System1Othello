"""Reference search: the regret oracle (Test B/D) and the minimax backend's brain.

Both run in the native core (native/ob.c). With `empties <= exact_empties` every move
is scored exactly, as the final disc differential under perfect play. Otherwise it is
scored by a depth-limited alpha-beta search over a static eval ("eval points": corners,
squares next to empty corners, mobility, frontier; a decided game scores
+-(10000 + discs)). That eval is deliberately not the heuristic backend's square table,
so the midgame proxy doesn't favour the heuristic by construction.
"""
from __future__ import annotations

from s1othello import native
from s1othello.engine import Board, empties, legal_moves

EXACT_EMPTIES = 14  # in-game default: ~40 ms per move in C
WIN_SCORE = 10000   # midgame search: a decided game scores +-(WIN_SCORE + discs)


def move_values(board: Board, player: str, depth: int = 6,
                exact_empties: int = EXACT_EMPTIES) -> tuple[dict[str, int], bool]:
    """({coord: value}, exact) for every legal move of `player`, from `player`'s view."""
    exact = empties(board) <= exact_empties
    vals = native.move_values(board, player, depth, exact)
    if not vals:
        raise ValueError(f"no legal moves for {player}")
    return vals, exact


def best_move(board: Board, player: str, depth: int = 6,
              exact_empties: int = EXACT_EMPTIES) -> tuple[str, dict[str, int]]:
    """(best coord, {coord: value}). Ties go to the first move in engine order."""
    vals, _ = move_values(board, player, depth, exact_empties)
    order = legal_moves(board, player)
    best = max(order, key=lambda m: vals[m])
    return best, vals
