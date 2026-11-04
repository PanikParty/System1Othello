"""Greedy baseline: play the move that flips the most discs right now. The naive
"immediate reward" policy that Othello punishes, so it marks where judgment starts."""
from __future__ import annotations

import time

from s1othello.backends.base import Answer, DecisionResult
from s1othello.backends.heuristic import scores_to_probs
from s1othello.engine import apply_move, disc_counts


def _board(state: dict) -> tuple[str, ...]:
    return tuple(state["board"][str(i + 1)] for i in range(8))


class GreedyBackend:
    name = "greedy"

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        board = _board(state)
        player = "B" if state["you_play"] == "black" else "W"
        idx = 0 if player == "B" else 1
        before = disc_counts(board)[idx]
        answers = {}
        for key, q in questions.items():
            scored = {o: disc_counts(apply_move(board, player, o))[idx] - before for o in q["criteria"]}
            choice = max(scored, key=scored.get)
            answers[key] = Answer(type="choice", value=choice, probabilities=scores_to_probs(scored))
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000, model="greedy")
