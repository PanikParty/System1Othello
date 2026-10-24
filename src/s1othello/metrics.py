"""Test B (move regret) and Test C (full-game outcome) metrics."""
from __future__ import annotations

from dataclasses import dataclass, field

from s1othello.engine import disc_counts
from s1othello.solver import best_move


@dataclass
class RegretSample:
    coord: str
    chosen: str
    regret: float  # V(s, a*) - V(s, a_model), >= 0, lower is better
    is_best: bool
    confidence: float | None
    latency_ms: float
    used_fallback: bool


def move_regret(board, player: str, chosen_move: str, depth: int = 6) -> RegretSample:
    best, values = best_move(board, player, depth=depth)
    regret = values[best] - values[chosen_move]
    return RegretSample(coord="?", chosen=chosen_move, regret=regret,
                        is_best=(chosen_move == best), confidence=None,
                        latency_ms=0.0, used_fallback=False)


@dataclass
class GameResult:
    backend_black: str
    backend_white: str
    black_discs: int
    white_discs: int
    winner: str | None  # "B" / "W" / None (draw)
    plies: int
    illegal_or_fallback_black: int
    illegal_or_fallback_white: int
    avg_latency_ms_black: float
    avg_latency_ms_white: float


@dataclass
class EvalSummary:
    backend: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    disc_diff_sum: int = 0
    fallback_count: int = 0
    move_count: int = 0
    latencies_ms: list = field(default_factory=list)
    regrets: list = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0

    @property
    def fallback_rate(self) -> float:
        return self.fallback_count / self.move_count if self.move_count else 0.0

    @property
    def avg_regret(self) -> float | None:
        return sum(self.regrets) / len(self.regrets) if self.regrets else None

    @property
    def p50_latency_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        s = sorted(self.latencies_ms)
        return s[len(s) // 2]

    @property
    def p95_latency_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        s = sorted(self.latencies_ms)
        return s[int(len(s) * 0.95) - 1] if len(s) > 1 else s[0]
