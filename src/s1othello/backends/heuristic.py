"""Handwritten positional heuristic: a classic square-weight table, no search and no
lookahead. Baseline, fallback target and label source (same role as s1doom's heuristic)."""
from __future__ import annotations

import time

from s1othello.backends.base import Answer, DecisionResult
from s1othello.engine import coord_to_rc

# corners strong, squares next to corners weak, edges good, centre mild
SQUARE_WEIGHTS = [
    [120, -20, 20, 5, 5, 20, -20, 120],
    [-20, -40, -5, -5, -5, -5, -40, -20],
    [20, -5, 15, 3, 3, 15, -5, 20],
    [5, -5, 3, 3, 3, 3, -5, 5],
    [5, -5, 3, 3, 3, 3, -5, 5],
    [20, -5, 15, 3, 3, 15, -5, 20],
    [-20, -40, -5, -5, -5, -5, -40, -20],
    [120, -20, 20, 5, 5, 20, -20, 120],
]


def scores_to_probs(scored: dict[str, float]) -> dict[str, float]:
    """Min-max scaled scores, normalised: a ranking, not a calibrated probability."""
    lo, hi = min(scored.values()), max(scored.values())
    span = (hi - lo) or 1.0
    raw = {o: (v - lo) / span + 0.01 for o, v in scored.items()}
    tot = sum(raw.values())
    return {o: v / tot for o, v in raw.items()}


class HeuristicBackend:
    name = "heuristic"

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        answers = {}
        for key, q in questions.items():
            scored = {o: SQUARE_WEIGHTS[coord_to_rc(o)[0]][coord_to_rc(o)[1]] for o in q["criteria"]}
            choice = max(scored, key=scored.get)
            answers[key] = Answer(type="choice", value=choice, probabilities=scores_to_probs(scored))
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000, model="heuristic")
