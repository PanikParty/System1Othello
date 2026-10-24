from __future__ import annotations

import random
import time

from s1othello.backends.base import Answer, DecisionResult


class RandomBackend:
    """Uniform over legal options. Fallback is disabled for this one so it
    stays a true floor (mirrors System1Doom's random backend)."""

    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        answers = {}
        for key, q in questions.items():
            options = list(q["criteria"].keys())
            choice = self._rng.choice(options)
            probs = {o: (1.0 if o == choice else 0.0) for o in options}
            answers[key] = Answer(type="choice", value=choice, probabilities=probs)
        return DecisionResult(answers=answers, latency_ms=(time.perf_counter() - t0) * 1000, model="random")
