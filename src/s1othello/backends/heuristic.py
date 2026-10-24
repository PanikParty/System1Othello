"""Handwritten positional heuristic: corner/edge weights + mobility, no search.
Baseline, fallback target, and label source -- same role as s1doom's heuristic."""
from __future__ import annotations

import time

from s1othello.backends.base import Answer, DecisionResult
from s1othello.engine import coord_to_rc
from s1othello.solver import _W


class HeuristicBackend:
    name = "heuristic"

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        answers = {}
        for key, q in questions.items():
            options = list(q["criteria"].keys())
            scored = {o: _W[coord_to_rc(o)[0]][coord_to_rc(o)[1]] for o in options}
            lo, hi = min(scored.values()), max(scored.values())
            span = (hi - lo) or 1.0
            probs = {o: (v - lo) / span + 0.01 for o, v in scored.items()}
            tot = sum(probs.values())
            probs = {o: v / tot for o, v in probs.items()}
            choice = max(scored, key=scored.get)
            answers[key] = Answer(type="choice", value=choice, probabilities=probs)
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000, model="heuristic")
