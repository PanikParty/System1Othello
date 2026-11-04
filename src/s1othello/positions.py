"""Test B/D position sets: generated once, solved by the oracle, frozen to positions/*.jsonl.

Positions come from self-play by a mix of non-model policies (random, greedy, heuristic,
minimax-d1/d2, each with epsilon-random moves) starting from seeded random openings. No
backend under test plays any part in generating them, so none can have been tuned on them.
Only positions with >= 2 legal moves are kept (a forced move is not a decision).

Phase buckets (by empty squares; Test D's held-out strata):
    opening 45-56 | midgame 30-44 | late 21-29 | endgame 15-20 | final 1-14
Tags (overlapping): corner_available, x_square_legal, can_force_pass, few_moves (2-3
legal), greedy_trap (the max-flips move loses >= 4 discs / 15 points), outcome_critical (exact: some
legal move changes the game-theoretic result).

Oracle: exact final disc differential when empties <= exact_empties (default 20), else a
depth-limited native search in eval points (a proxy, see solver.py; clamped to
+-PROXY_CLAMP when scoring regret).
"""
from __future__ import annotations

import asyncio
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from s1othello.backends.greedy import GreedyBackend
from s1othello.backends.heuristic import HeuristicBackend
from s1othello.backends.minimax import MinimaxBackend
from s1othello.engine import Board, Position, apply_move, disc_counts, empties, legal_moves, other
from s1othello.state import CORNERS, PromptSet, build_questions, build_state, square_kind

PHASES = [("opening", 45, 56), ("midgame", 30, 44), ("late", 21, 29), ("endgame", 15, 20), ("final", 1, 14)]


def phase_of(e: int) -> str | None:
    for name, lo, hi in PHASES:
        if lo <= e <= hi:
            return name
    return None


def _policy_move(kind: str, ps: PromptSet, board: Board, player: str, rng: random.Random) -> str:
    moves = legal_moves(board, player)
    if kind == "random" or rng.random() < 0.15:
        return rng.choice(moves)
    backend = {"greedy": GreedyBackend(), "heuristic": HeuristicBackend(),
               "minimax-d1": MinimaxBackend(1), "minimax-d2": MinimaxBackend(2)}[kind]
    q = build_questions(ps, board, player, moves)
    res = asyncio.run(backend.system_one(build_state(ps, board, player, include_rules=False), q))
    return res.answers["move"].value


POLICIES = ["random", "greedy", "heuristic", "minimax-d1", "minimax-d2"]


def generate_pool(n_games: int, seed: int) -> list[tuple[Board, str]]:
    rng = random.Random(seed)
    ps = PromptSet.load("v1")
    seen: set = set()
    pool: list[tuple[Board, str]] = []
    for _ in range(n_games):
        pols = {"B": rng.choice(POLICIES), "W": rng.choice(POLICIES)}
        pos = Position.start()
        for _ in range(rng.randint(2, 6)):
            pos = pos.step(rng.choice(pos.legal()))
        while not pos.is_terminal():
            key = (pos.board, pos.to_move)
            if len(pos.legal()) >= 2 and key not in seen and phase_of(empties(pos.board)):
                seen.add(key)
                pool.append(key)
            pos = pos.step(_policy_move(pols[pos.to_move], ps, pos.board, pos.to_move, rng))
    return pool


def static_tags(board: Board, player: str) -> list[str]:
    moves = legal_moves(board, player)
    tags = []
    if any(m in CORNERS for m in moves):
        tags.append("corner_available")
    if any(square_kind(board, m) == "x-square" for m in moves):
        tags.append("x_square_legal")
    if any(not legal_moves(apply_move(board, player, m), other(player)) for m in moves):
        tags.append("can_force_pass")
    if len(moves) <= 3:
        tags.append("few_moves")
    return tags


def _solve_one(args: tuple) -> dict:
    board, player, depth, exact_empties = args
    from s1othello.solver import move_values

    values, exact = move_values(board, player, depth=depth, exact_empties=exact_empties)
    return {"values": values, "exact": exact}


GREEDY_TRAP_DISCS = 4    # exact: the max-flips move costs >= 4 final discs
GREEDY_TRAP_POINTS = 15  # proxy: >= 15 eval points (half a corner)


def oracle_tags(board: Board, player: str, values: dict[str, int], exact: bool) -> list[str]:
    best = max(values.values())
    idx = 0 if player == "B" else 1
    before = disc_counts(board)[idx]
    flips = {m: disc_counts(apply_move(board, player, m))[idx] - before for m in values}
    greedy = max(legal_moves(board, player), key=lambda m: flips[m])
    tags = []
    if best - values[greedy] >= (GREEDY_TRAP_DISCS if exact else GREEDY_TRAP_POINTS):
        tags.append("greedy_trap")
    if exact and len({(v > 0) - (v < 0) for v in values.values()}) > 1:
        tags.append("outcome_critical")
    return tags


def build_set(per_phase: int, seed: int, depth: int = 10, exact_empties: int = 20,
              workers: int = 1, n_games: int = 4000) -> list[dict]:
    pool = generate_pool(n_games, seed)
    rng = random.Random(seed + 1)
    by_phase: dict[str, list] = {p[0]: [] for p in PHASES}
    for b, pl in pool:
        by_phase[phase_of(empties(b))].append((b, pl))
    chosen: list[tuple[str, Board, str]] = []
    for name, _, _ in PHASES:
        cand = by_phase[name]
        if len(cand) < per_phase:
            raise RuntimeError(f"phase {name}: only {len(cand)} positions in the pool")
        chosen += [(name, b, pl) for b, pl in rng.sample(cand, per_phase)]
    jobs = [(b, pl, depth, exact_empties) for _, b, pl in chosen]
    if workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            solved = list(ex.map(_solve_one, jobs, chunksize=1))
    else:
        solved = [_solve_one(j) for j in jobs]
    rows = []
    for i, ((phase, b, pl), s) in enumerate(zip(chosen, solved)):
        rows.append({
            "id": f"p{i:04d}", "board": list(b), "player": pl, "empties": empties(b), "phase": phase,
            "n_legal": len(s["values"]), "tags": static_tags(b, pl) + oracle_tags(b, pl, s["values"], s["exact"]),
            "exact": s["exact"], "values": s["values"],
            "oracle": {"depth": depth, "exact_empties": exact_empties},
        })
    return rows


def save_set(rows: list[dict], path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write(json.dumps({"meta": meta}) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")


def load_set(path: Path) -> tuple[dict, list[dict]]:
    lines = [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    return lines[0]["meta"], lines[1:]


PROXY_CLAMP = 200  # proxy values are clamped to +-this: a search that sees a decided game
                  # (+-10000) would otherwise dominate every mean


def regret_of(row: dict, move: str) -> dict:
    """Regret of `move` in this position: exact discs, or clamped eval points (proxy)."""
    values = row["values"]
    if not row["exact"]:
        values = {m: max(-PROXY_CLAMP, min(PROXY_CLAMP, v)) for m, v in values.items()}
    best = max(values.values())
    v = values[move]
    sign = lambda x: (x > 0) - (x < 0)  # noqa: E731
    out = {"regret": best - v, "is_best": v == best,
           "random_regret": best - sum(values.values()) / len(values)}
    if row["exact"]:
        out["outcome_lost"] = sign(v) < sign(best)
    return out
