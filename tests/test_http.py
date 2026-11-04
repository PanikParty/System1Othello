import asyncio
import json

import httpx
import pytest

from s1othello.agent import decide
from s1othello.backends.http import SystemOneHTTP
from s1othello.engine import initial_board


def _server(handler):
    seen = []

    def h(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append((req, body))
        return handler(body)
    return httpx.MockTransport(h), seen


def test_choice_roundtrip_and_auth_header(ps):
    def handler(body):
        opts = list(body["questions"]["move"]["criteria"])
        dist = [0.1] * len(opts)
        dist[2] = 1 - 0.1 * (len(opts) - 1)
        return httpx.Response(200, json={"answers": {"move": {"type": "choice", "distribution": dist}},
                                         "usage": {"input_tokens": 321}, "model": "fake"})
    transport, seen = _server(handler)
    be = SystemOneHTTP("fake", "http://x", "m", "secret", transport=transport)
    d, moves, _, _ = asyncio.run(decide(be, ps, initial_board(), "B"))
    assert d.source == "model" and d.move == moves[2] and d.confidence == pytest.approx(0.7)
    req, body = seen[0]
    assert req.url.path == "/v1/systemone" and req.headers["authorization"] == "Bearer secret"
    assert body["model"] == "m" and body["state"]["you_play"] == "black"
    assert be.input_tokens == 321


def test_http_error_falls_back(ps):
    transport, _ = _server(lambda body: httpx.Response(400, json={"error": "bad"}))
    be = SystemOneHTTP("fake", "http://x/v1/systemone", None, None, transport=transport)
    d, _, _, _ = asyncio.run(decide(be, ps, initial_board(), "B"))
    assert d.source == "fallback" and "HTTP 400" in d.error


def test_missing_answer_falls_back(ps):
    transport, _ = _server(lambda body: httpx.Response(200, json={"answers": {}}))
    be = SystemOneHTTP("fake", "http://x", None, None, transport=transport)
    d, _, _, _ = asyncio.run(decide(be, ps, initial_board(), "B"))
    assert d.source == "fallback" and "missing" in d.error
