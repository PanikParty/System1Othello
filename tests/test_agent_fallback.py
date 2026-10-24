import asyncio

from s1othello.agent import decide
from s1othello.backends.base import Answer, DecisionResult
from s1othello.engine import initial_board


class _BrokenBackend:
    name = "broken"

    async def system_one(self, state, questions):
        raise RuntimeError("simulated backend outage")


class _IllegalBackend:
    name = "illegal"

    async def system_one(self, state, questions):
        return DecisionResult(answers={"move": Answer(type="choice", value="A1", probabilities={"A1": 1.0})})


def test_fallback_on_backend_error():
    b = initial_board()
    d = asyncio.run(decide(_BrokenBackend(), b, "B"))
    assert d.used_fallback is True
    assert d.move in ["C4", "D3", "E6", "F5"]


def test_fallback_on_illegal_choice():
    b = initial_board()
    d = asyncio.run(decide(_IllegalBackend(), b, "B"))
    assert d.used_fallback is True
    assert d.move in ["C4", "D3", "E6", "F5"]
