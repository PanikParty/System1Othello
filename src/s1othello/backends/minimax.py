"""Search-engine backend: wraps the negamax/exact solver as a DecisionBackend
so it can play full games and act as the reference in direct-play comparisons
(Test C) using the exact same harness as the model backends."""
from __future__ import annotations

import time

from s1othello.backends.base import Answer, DecisionResult
from s1othello.engine import coord_to_rc
from s1othello.solver import best_move


class MinimaxBackend:
    name = "minimax"

    def __init__(self, depth: int = 6) -> None:
        self.depth = depth

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        board = tuple(state["board"])
        player = state["current_player"]
        _, values = best_move(board, player, depth=self.depth)
        lo, hi = min(values.values()), max(values.values())
        span = (hi - lo) or 1.0
        probs_raw = {o: (v - lo) / span + 0.01 for o, v in values.items()}
        tot = sum(probs_raw.values())
        probs = {o: v / tot for o, v in probs_raw.items()}
        answers = {}
        for key, q in questions.items():
            options = list(q["criteria"].keys())
            vals = {o: values[o] for o in options}
            choice = max(vals, key=vals.get)
            p = {o: probs[o] for o in options}
            answers[key] = Answer(type="choice", value=choice, probabilities=p)
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000,
                              model=f"minimax-d{self.depth}", raw={"values": values})
