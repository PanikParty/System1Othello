"""Test C: full games between two backends from a given start position."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from s1othello.agent import call_row, decide
from s1othello.backends.base import DecisionBackend
from s1othello.engine import Position, disc_counts
from s1othello.state import PromptSet


@dataclass
class SideStats:
    model: int = 0
    fallback: int = 0
    forced: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add(self, source: str, latency_ms: float, error: str | None) -> None:
        if source == "forced":
            self.forced += 1
            return
        setattr(self, source, getattr(self, source) + 1)
        self.latencies_ms.append(latency_ms)
        if error:
            self.errors.append(error)


async def play_game(black: DecisionBackend, white: DecisionBackend, ps: PromptSet, start: Position,
                    log: Callable[[dict], None] | None = None, verbose: bool = False, **meta) -> dict:
    pos = start
    side = {"B": SideStats(), "W": SideStats()}
    plies = 0
    moves: list[str] = []
    while not pos.is_terminal():
        backend = black if pos.to_move == "B" else white
        d, legal, _, _ = await decide(backend, ps, pos.board, pos.to_move)
        side[pos.to_move].add(d.source, d.latency_ms, d.error)
        if log is not None and d.source != "forced":
            log(call_row(backend.name, ps, d, pos.board, pos.to_move, legal, ply=plies, **meta))
        if verbose:
            tag = "" if d.source == "model" else f" ({d.source})"
            conf = f" p={d.confidence:.2f}" if d.confidence is not None else ""
            print(f"  ply {plies:>2} {pos.to_move} {backend.name:>14} -> {d.move}{conf}{tag}")
        moves.append(d.move)
        pos = pos.step(d.move)
        plies += 1
    b, w = disc_counts(pos.board)
    out = {"black": black.name, "white": white.name, "black_discs": b, "white_discs": w,
           "winner": "B" if b > w else ("W" if w > b else None), "plies": plies, "moves": moves,
           "final_board": list(pos.board), **meta}
    for c, s in side.items():
        out[c] = {"model": s.model, "fallback": s.fallback, "forced": s.forced,
                  "latencies_ms": [round(x, 2) for x in s.latencies_ms], "errors": s.errors[:5]}
    return out


def seat_view(game: dict, colour: str) -> dict:
    """One game from one side's point of view."""
    mine, theirs = (game["black_discs"], game["white_discs"]) if colour == "B" else (game["white_discs"], game["black_discs"])
    w = game["winner"]
    return {"colour": colour, "disc_diff": mine - theirs,
            "score": 1.0 if w == colour else (0.5 if w is None else 0.0), **game[colour]}
