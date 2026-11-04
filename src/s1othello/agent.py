"""One DecisionBackend call -> one validated move.

- A position with a single legal move is `forced`: no call is made, and it is excluded
  from latency, fallback and confidence statistics (there is no decision to make).
- A backend error, illegal choice or malformed answer falls back to the heuristic. That
  move is labelled `fallback` and is never counted as model output.
- Every decision can be logged as one calls.jsonl row carrying `prompt_version`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from s1othello.backends.base import DecisionBackend, DecisionResult
from s1othello.backends.heuristic import HeuristicBackend
from s1othello.engine import Board
from s1othello.state import PromptSet, state_and_questions

_FALLBACK = HeuristicBackend()


@dataclass
class Decision:
    move: str
    source: str  # "model" | "fallback" | "forced"
    latency_ms: float
    confidence: float | None  # the backend's max_prob for its own answer (None if forced/fallback)
    probabilities: dict[str, float] = field(default_factory=dict)
    result: DecisionResult | None = None
    error: str | None = None

    @property
    def used_fallback(self) -> bool:
        return self.source == "fallback"


async def decide(backend: DecisionBackend, ps: PromptSet, board: Board, player: str,
                 allow_fallback: bool = True) -> tuple[Decision, list[str], dict, dict]:
    """Returns (decision, legal moves, state, questions)."""
    state, questions, moves = state_and_questions(ps, board, player)
    if len(moves) == 1:
        return Decision(moves[0], "forced", 0.0, None), moves, state, questions
    t0 = time.perf_counter()
    try:
        res = await backend.system_one(state, questions)
        ans = res.answers["move"]
        if ans.value not in moves:
            raise ValueError(f"illegal choice {ans.value!r} not in {moves}")
        return (Decision(ans.value, "model", (time.perf_counter() - t0) * 1000, ans.max_prob,
                         ans.probabilities, res), moves, state, questions)
    except Exception as e:  # noqa: BLE001 -- any backend failure triggers fallback
        if not allow_fallback:
            raise
        fb = await _FALLBACK.system_one(state, questions)
        return (Decision(fb.answers["move"].value, "fallback", (time.perf_counter() - t0) * 1000, None,
                         {}, None, error=f"{type(e).__name__}: {e}"[:300]), moves, state, questions)


def call_row(backend_name: str, ps: PromptSet, d: Decision, board: Board, player: str,
             moves: list[str], **extra) -> dict:
    """calls.jsonl row for one decision. The state is reconstructable from board+player."""
    res = d.result
    return {
        "backend": backend_name, "prompt_version": ps.version, "player": player,
        "board": list(board), "legal": moves, "move": d.move, "source": d.source,
        "confidence": d.confidence, "probabilities": d.probabilities or None,
        "latency_ms": round(d.latency_ms, 2),
        "server_latency_ms": round(res.latency_ms, 2) if res else None,
        "usage": res.usage if res and res.usage else None,
        "model": res.model if res else None,
        "route": (res.raw or {}).get("route") if res else None,
        "error": d.error, **extra,
    }
