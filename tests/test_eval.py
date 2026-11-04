import asyncio
import json

from s1othello import evaluate
from s1othello.backends.heuristic import HeuristicBackend
from s1othello.backends.random_ import RandomBackend
from s1othello.engine import Position
from s1othello.games import play_game, seat_view
from s1othello.openings import make_openings
from s1othello.positions import build_set, load_set, regret_of, save_set
from s1othello.report import build_report
from s1othello.evaluate import summarize_regret
from s1othello.stats import percentile, wilson


def test_openings_are_seeded_distinct_and_balanced():
    a, b = make_openings(5, seed=3), make_openings(5, seed=3)
    assert a == b and len({(p.board, p.to_move) for p in a}) == 5
    assert make_openings(5, seed=4) != a


def test_game_accounting(ps):
    g = asyncio.run(play_game(HeuristicBackend(), RandomBackend(1), ps, Position.start()))
    assert g["black_discs"] + g["white_discs"] <= 64 and g["plies"] == len(g["moves"])
    assert sum(g[c][k] for c in "BW" for k in ("model", "fallback", "forced")) == g["plies"]
    assert g["B"]["fallback"] == g["W"]["fallback"] == 0
    v = seat_view(g, "B")
    assert v["disc_diff"] == g["black_discs"] - g["white_discs"]


def test_stats():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([5.0, 1.0], 95) > percentile([5.0, 1.0], 50)
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi


def test_regret_semantics():
    row = {"values": {"A1": 10, "B1": 4, "C1": -2}, "exact": True}
    assert regret_of(row, "A1") == {"regret": 0, "is_best": True, "random_regret": 6.0, "outcome_lost": False}
    assert regret_of(row, "C1")["outcome_lost"] is True
    proxy = {"values": {"A1": 10010, "B1": 0}, "exact": False}
    assert regret_of(proxy, "B1")["regret"] == 200  # clamped


def test_build_set_and_regret_eval(tmp_path, monkeypatch):
    rows = build_set(per_phase=2, seed=1, depth=2, exact_empties=10, n_games=40)
    assert len(rows) == 10 and {r["phase"] for r in rows} == {"opening", "midgame", "late", "endgame", "final"}
    assert all(r["n_legal"] >= 2 and set(r["values"]) for r in rows)
    path = tmp_path / "pos.jsonl"
    save_set(rows, path, {"seed": 1})
    meta, back = load_set(path)
    assert meta == {"seed": 1} and back == rows

    monkeypatch.setattr(evaluate, "RUNS_DIR", tmp_path / "runs")
    run = evaluate.run_eval({"mode": "regret", "tag": "t", "backends": ["heuristic", "minimax-d2"], "seed": 0,
                             "prompt_version": "v1", "concurrency": 1, "positions": str(path), "limit": None})
    s = json.loads((run / "summary.json").read_text())["summaries"]
    assert [x["backend"] for x in s] == ["heuristic", "minimax-d2"]
    assert s[0]["decisions"] == 10 and s[0]["fallback"] == 0
    assert (run / "calls" / "heuristic.jsonl").exists()

    run = evaluate.run_eval({"mode": "games", "tag": "t", "backends": ["random"], "seed": 0, "prompt_version": "v1",
                             "concurrency": 2, "opponent": "heuristic", "openings": 2})
    g = json.loads((run / "summary.json").read_text())["summaries"][0]
    assert g["games"] == 4 and g["openings"] == 2 and g["wins"] + g["draws"] + g["losses"] == 4
    text = build_report(tmp_path / "runs")
    assert "Test C" in text and "Test B" in text and "| random |" in text


def test_regret_summary_excludes_fallback_moves():
    def r(source, best, regret):
        return {"source": source, "is_best": best, "regret": regret, "random_regret": 5.0, "exact": True,
                "phase": "final", "tags": [], "latency_ms": 1.0, "outcome_lost": False}
    s = summarize_regret([r("model", True, 0), r("fallback", False, 9)])
    assert s["exact"]["n"] == 1 and s["exact"]["regret"] == 0 and s["fallback_rate"] == 0.5
