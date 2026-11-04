from __future__ import annotations

import random
import time

from s1othello.backends.base import Answer, DecisionResult


class RandomBackend:
    """Uniform over legal options: the floor. It cannot fail, so it never falls back."""

    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        answers = {}
        for key, q in questions.items():
            options = list(q["criteria"].keys())
            choice = self._rng.choice(options)
            answers[key] = Answer(type="choice", value=choice,
                                  probabilities={o: 1 / len(options) for o in options})
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000, model="random")
