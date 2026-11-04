import asyncio

from s1othello.agent import call_row, decide
from s1othello.backends.base import Answer, DecisionResult
from s1othello.engine import initial_board


class _Broken:
    name = "broken"
    calls = 0

    async def system_one(self, state, questions):
        self.calls += 1
        raise RuntimeError("simulated backend outage")


class _Illegal:
    name = "illegal"

    async def system_one(self, state, questions):
        return DecisionResult(answers={"move": Answer(type="choice", value="A1", probabilities={"A1": 1.0})})


class _Fixed:
    name = "fixed"

    async def system_one(self, state, questions):
        opts = list(questions["move"]["criteria"])
        return DecisionResult(answers={"move": Answer(type="choice", value=opts[-1],
                                                      probabilities={o: 0.1 for o in opts[:-1]} | {opts[-1]: 0.7})})


def test_fallback_on_backend_error(ps):
    d, moves, _, _ = asyncio.run(decide(_Broken(), ps, initial_board(), "B"))
    assert d.source == "fallback" and d.used_fallback and d.move in moves
    assert d.confidence is None and "outage" in d.error


def test_fallback_on_illegal_choice(ps):
    d, moves, _, _ = asyncio.run(decide(_Illegal(), ps, initial_board(), "B"))
    assert d.source == "fallback" and d.move in moves


def test_model_answer_and_log_row(ps):
    d, moves, _, _ = asyncio.run(decide(_Fixed(), ps, initial_board(), "B"))
    assert d.source == "model" and d.move == "E6" and abs(d.confidence - 0.7) < 1e-9
    row = call_row("fixed", ps, d, initial_board(), "B", moves, ply=0)
    assert row["prompt_version"] == "v1" and row["source"] == "model" and row["ply"] == 0


def test_forced_move_makes_no_call(ps):
    # Black's only legal move is F3 (flanking G2 against H1).
    board = (".......B", "......W.", "........", "........", "........", "........", "........", "........")
    be = _Broken()
    d, moves, _, _ = asyncio.run(decide(be, ps, board, "B"))
    assert moves == ["F3"] and d.source == "forced" and be.calls == 0
