"""Turns one DecisionBackend call into a validated move, with fallback to the
heuristic backend on backend error / illegal / malformed answer (same
reliability pattern as System1Doom's agent -- the model's unreliability must
not crash the harness, and fallback frequency is itself a benchmark metric)."""
from __future__ import annotations

import time
from dataclasses import dataclass

from s1othello.backends.base import BackendError, DecisionBackend, DecisionResult
from s1othello.backends.heuristic import HeuristicBackend
from s1othello.state import state_and_questions

_FALLBACK = HeuristicBackend()


@dataclass
class Decision:
    move: str
    used_fallback: bool
    latency_ms: float
    confidence: float | None
    result: DecisionResult | None
    error: str | None = None


async def decide(backend: DecisionBackend, board, player: str, allow_fallback: bool = True) -> Decision:
    state, questions, moves = state_and_questions(board, player)
    t0 = time.perf_counter()
    try:
        res = await backend.system_one(state, questions)
        choice = res.answers["move"].value
        if choice not in moves:
            raise BackendError(f"{backend.name}: illegal choice {choice!r} not in {moves}")
        return Decision(move=choice, used_fallback=False,
                        latency_ms=(time.perf_counter() - t0) * 1000,
                        confidence=res.answers["move"].max_prob, result=res)
    except Exception as e:  # noqa: BLE001 -- any backend failure triggers fallback
        if not allow_fallback:
            raise
        fb = await _FALLBACK.system_one(state, questions)
        choice = fb.answers["move"].value
        return Decision(move=choice, used_fallback=True,
                        latency_ms=(time.perf_counter() - t0) * 1000,
                        confidence=fb.answers["move"].max_prob, result=fb, error=str(e))
