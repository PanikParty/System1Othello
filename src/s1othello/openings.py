"""Seeded Test C start positions. Every backend here is deterministic, so without varied
starts "20 episodes" would be the same two games replayed. Each opening is a few uniform
random plies from the initial position, kept only if a depth-8 search scores it roughly
even, and each is played twice with colours swapped (a paired design)."""
from __future__ import annotations

import random

from s1othello.engine import Position
from s1othello.solver import move_values

BALANCE_LIMIT = 20  # |depth-8 eval| in eval points; ~ one corner's worth is 30


def make_openings(n: int, seed: int = 0, plies: int = 6, balance_limit: int | None = BALANCE_LIMIT) -> list[Position]:
    rng = random.Random(seed)
    out: list[Position] = []
    seen: set = set()
    tries = 0
    while len(out) < n:
        tries += 1
        if tries > 1000 * n:
            raise RuntimeError(f"only found {len(out)} openings for seed {seed}")
        pos = Position.start()
        for _ in range(plies):
            pos = pos.step(rng.choice(pos.legal()))
        key = (pos.board, pos.to_move)
        if key in seen:
            continue
        seen.add(key)
        if balance_limit is not None:
            vals, _ = move_values(pos.board, pos.to_move, depth=8)
            if abs(max(vals.values())) > balance_limit:
                continue
        out.append(pos)
    return out
