import asyncio

from s1othello.agent import decide
from s1othello.backends.base import Answer, DecisionResult
from s1othello.backends.router import RouterBackend
from s1othello.engine import initial_board


class _Model:
    def __init__(self, probs):
        self.name, self.probs = "m", probs

    async def system_one(self, state, questions):
        p = {o: self.probs.get(o, 0.0) for o in questions["move"]["criteria"]}
        return DecisionResult(answers={"move": Answer(type="choice", value=max(p, key=p.get), probabilities=p)})


class _LastOption:
    """Stands in for search: picks the last option it is offered."""
    name = "s"

    async def system_one(self, state, questions):
        return DecisionResult(answers={"move": Answer(type="choice", value=list(questions["move"]["criteria"])[-1])})


def _route(router, ps):
    d, _, _, _ = asyncio.run(decide(router, ps, initial_board(), "B"))
    return d.move, d.result.raw["route"]


def test_gate_keeps_confident_model_moves(ps):
    r = RouterBackend(_Model({"D3": 0.9, "C4": 0.1}), _LastOption(), mode="gate", threshold=0.5)
    assert _route(r, ps) == ("D3", "model")


def test_gate_hands_unsure_positions_to_search(ps):
    r = RouterBackend(_Model({"D3": 0.4, "C4": 0.3, "F5": 0.3}), _LastOption(), mode="gate", threshold=0.5)
    assert _route(r, ps) == ("E6", "search")


def test_prune_searches_only_the_top_k(ps):
    r = RouterBackend(_Model({"D3": 0.5, "C4": 0.3, "F5": 0.15, "E6": 0.05}), _LastOption(), mode="prune", top_k=2)
    assert _route(r, ps) == ("C4", "prune")
