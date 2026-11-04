"""Search-engine backend: native alpha-beta at a fixed depth, exact in the last
`exact_empties` squares. The search reference and the default Test C opponent, run
through the same harness as the model backends."""
from __future__ import annotations

import time

from s1othello.backends.base import Answer, DecisionResult
from s1othello.backends.greedy import _board
from s1othello.backends.heuristic import scores_to_probs
from s1othello.solver import EXACT_EMPTIES, move_values


class MinimaxBackend:
    def __init__(self, depth: int = 4, exact_empties: int = EXACT_EMPTIES, name: str | None = None) -> None:
        self.depth = depth
        self.exact_empties = exact_empties
        self.name = name or f"minimax-d{depth}"

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        board = _board(state)
        player = "B" if state["you_play"] == "black" else "W"
        values, exact = move_values(board, player, self.depth, self.exact_empties)
        answers = {}
        for key, q in questions.items():
            vals = {o: values[o] for o in q["criteria"]}
            choice = max(vals, key=vals.get)  # criteria are in engine order, so ties are stable
            answers[key] = Answer(type="choice", value=choice, probabilities=scores_to_probs(vals))
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000,
                              model=self.name, raw={"values": values, "exact": exact})
