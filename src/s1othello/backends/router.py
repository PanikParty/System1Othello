"""Confidence-gated hybrid (PLAN.md §3): the System One model decides, search steps in.

    mode "gate":  play the model's move when its max_prob >= threshold, else ask search.
    mode "prune": search only among the model's top-k moves (the model as a move prior).

Errors from the model propagate, so agent.decide labels them `fallback` as usual. The
route taken is reported in DecisionResult.raw["route"] ("model" | "search" | "prune").
"""
from __future__ import annotations

import time

from s1othello.backends.base import Answer, DecisionBackend, DecisionResult


class RouterBackend:
    def __init__(self, model: DecisionBackend, search: DecisionBackend, mode: str = "gate",
                 threshold: float = 0.5, top_k: int = 3, name: str | None = None) -> None:
        if mode not in ("gate", "prune"):
            raise ValueError(f"router mode {mode!r} (gate | prune)")
        self.model, self.search, self.mode = model, search, mode
        self.threshold, self.top_k = threshold, top_k
        self.name = name or f"{model.name}+{search.name}-{mode}"

    async def system_one(self, state: dict, questions: dict) -> DecisionResult:
        t0 = time.perf_counter()
        res = await self.model.system_one(state, questions)
        a = res.answers["move"]
        q = questions["move"]
        route, choice = "model", a.value
        if self.mode == "gate" and a.max_prob < self.threshold:
            route = "search"
            choice = (await self.search.system_one(state, questions)).answers["move"].value
        elif self.mode == "prune" and len(q["criteria"]) > self.top_k:
            order = list(q["criteria"])
            ranked = sorted(order, key=lambda o: (-a.probabilities.get(o, 0.0), order.index(o)))
            keep = set(ranked[: self.top_k])
            sub = {"move": {**q, "criteria": {o: t for o, t in q["criteria"].items() if o in keep}}}
            route = "prune"
            choice = (await self.search.system_one(state, sub)).answers["move"].value
        return DecisionResult(
            answers={"move": Answer(type="choice", value=choice, probabilities=a.probabilities,
                                    raw_confidence=a.raw_confidence)},
            latency_ms=(time.perf_counter() - t0) * 1000, usage=res.usage, model=res.model,
            raw={"route": route, "model_choice": a.value, "model_max_prob": a.max_prob})
