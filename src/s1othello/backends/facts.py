"""Facts baseline: a fixed rule over exactly the per-move facts prompt v2 hands a model
(state.move_features). Take a corner; avoid giving the opponent a corner; avoid
x-squares; then minimise opponent replies; then prefer edges; then fewer flips.

It answers the v2 control question: does a model add judgment beyond the facts it is given?
"""
from __future__ import annotations

import time

from s1othello.backends.base import Answer, DecisionResult
from s1othello.backends.greedy import _board
from s1othello.backends.heuristic import scores_to_probs
from s1othello.state import move_features


def facts_score(f: dict) -> float:
    s = 0.0
    s += 1000 if f["square"] == "corner" else 0
    s += 300 if f["opponent_passes"] else 0
    s -= 500 if f["opponent_gets_corner"] else 0
    s -= 200 if f["square"] == "x-square" else 0
    s -= 50 if f["square"] == "c-square" else 0
    s -= 10 * f["opponent_replies"]
    s += 5 if f["square"] == "edge" else 0
    s -= 0.5 * f["flips"]
    return s


class FactsBackend:
    name = "facts"

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        board = _board(state)
        player = "B" if state["you_play"] == "black" else "W"
        answers = {}
        for key, q in questions.items():
            scored = {o: facts_score(move_features(board, player, o)) for o in q["criteria"]}
            choice = max(scored, key=scored.get)
            answers[key] = Answer(type="choice", value=choice, probabilities=scores_to_probs(scored))
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000, model="facts")
