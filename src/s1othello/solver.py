"""Reference Othello engine: negamax + alpha-beta, exact near the endgame.

This is the "search baseline" and the regret oracle (Test B / V(s, a) in the
companion design doc). Not a model -- deterministic, reproducible, cacheable.
"""
from __future__ import annotations

from s1othello.engine import (
    Position,
    disc_counts,
    empties,
    other,
)

# Static positional weights (classic Othello heuristic: corners strong,
# cells adjacent to corners weak/dangerous, edges good, center mild).
_W = [
    [120, -20, 20, 5, 5, 20, -20, 120],
    [-20, -40, -5, -5, -5, -5, -40, -20],
    [20, -5, 15, 3, 3, 15, -5, 20],
    [5, -5, 3, 3, 3, 3, -5, 5],
    [5, -5, 3, 3, 3, 3, -5, 5],
    [20, -5, 15, 3, 3, 15, -5, 20],
    [-20, -40, -5, -5, -5, -5, -40, -20],
    [120, -20, 20, 5, 5, 20, -20, 120],
]
EXACT_EMPTIES_THRESHOLD = 8  # switch to exact disc-diff search this close to the end


def _static_eval(board, player: str) -> float:
    opp = other(player)
    score = 0.0
    for r in range(8):
        for c in range(8):
            v = board[r][c]
            if v == player:
                score += _W[r][c]
            elif v == opp:
                score -= _W[r][c]
    mob = len(Position(board, player).legal()) - len(Position(board, opp).legal())
    score += 10 * mob
    return score


def _exact_eval(board, player: str) -> float:
    b, w = disc_counts(board)
    diff = (b - w) if player == "B" else (w - b)
    return float(diff) * 1000  # dwarfs positional eval, used only at true terminal/exact leaves


def negamax(pos: Position, depth: int, alpha: float, beta: float, exact: bool,
            nodes: list[int] | None = None) -> float:
    """Returns value from pos.to_move's perspective. `exact` forces play-out to
    a true terminal state (used once few empties remain) rather than depth cutoff."""
    if nodes is not None:
        nodes[0] += 1
    if pos.is_terminal():
        return _exact_eval(pos.board, _mover_for_terminal(pos))
    if not exact and depth == 0:
        return _static_eval(pos.board, pos.to_move)

    moves = pos.legal()
    best = float("-inf")
    for m in moves:
        child = pos.step(m)
        if child.to_move == other(pos.to_move) or child.to_move == "":
            val = -negamax(child, depth - 1, -beta, -alpha, exact, nodes)
        else:
            # opponent passed, same player moves again -- not a sign flip
            val = negamax(child, depth - 1, alpha, beta, exact, nodes)
        best = max(best, val)
        alpha = max(alpha, val)
        if alpha >= beta:
            break
    return best


def _mover_for_terminal(pos: Position) -> str:
    # terminal Position has to_move == "", perspective doesn't matter for exact
    # eval since _exact_eval takes an explicit player; caller fixes it up.
    return "B"


def best_move(board, player: str, depth: int = 6) -> tuple[str, dict[str, float]]:
    """Search every legal move for `player`; return (best_coord, {coord: value}).
    Values are from `player`'s perspective (higher = better for `player`).
    Switches to exact endgame search automatically once few squares remain.
    """
    pos = Position(board, player)
    moves = pos.legal()
    if not moves:
        raise ValueError("no legal moves")
    exact = empties(board) <= EXACT_EMPTIES_THRESHOLD
    values: dict[str, float] = {}
    for m in moves:
        child = pos.step(m)
        if child.to_move == player:
            # opponent had no reply; same player moves again, no sign flip
            v = negamax(child, depth - 1, float("-inf"), float("inf"), exact)
        else:
            v = -negamax(child, depth - 1, float("-inf"), float("inf"), exact)
        if exact:
            v = _rescore_exact(board, player, m)
        values[m] = v
    best = max(values, key=values.get)
    return best, values


def _rescore_exact(board, player: str, move: str) -> float:
    """Exact game-theoretic disc differential after `move`, assuming perfect
    play by both sides to the true end of the game."""
    pos = Position(board, player).step(move)
    return _exact_solve(pos, player)


_EXACT_TT: dict[tuple, float] = {}


def _exact_ab(board, to_move: str, perspective: str, alpha: float, beta: float) -> float:
    pos = Position(board, to_move)
    if pos.is_terminal():
        b, w = disc_counts(board)
        return float((b - w) if perspective == "B" else (w - b))
    key = (board, to_move)
    cached = _EXACT_TT.get(key)
    if cached is not None:
        return cached
    maximizing = to_move == perspective
    best = float("-inf") if maximizing else float("inf")
    for m in pos.legal():
        child = pos.step(m)
        v = _exact_ab(child.board, child.to_move, perspective, alpha, beta)
        if maximizing:
            best = max(best, v)
            alpha = max(alpha, best)
        else:
            best = min(best, v)
            beta = min(beta, best)
        if alpha >= beta:
            break
    if len(_EXACT_TT) < 2_000_000:
        _EXACT_TT[key] = best
    return best


def _exact_solve(pos: Position, perspective: str) -> float:
    if pos.is_terminal():
        b, w = disc_counts(pos.board)
        return float((b - w) if perspective == "B" else (w - b))
    return _exact_ab(pos.board, pos.to_move, perspective, float("-inf"), float("inf"))
