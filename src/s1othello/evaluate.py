"""Batch evaluations. Each writes runs/<run_id>/ with
    config.json, games.jsonl | decisions.jsonl, calls/<backend>.jsonl, summary.json
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path

from s1othello.agent import call_row, decide
from s1othello.backends.factory import make_backend
from s1othello.games import play_game, seat_view
from s1othello.openings import make_openings
from s1othello.positions import PHASES, load_set, regret_of
from s1othello.state import PromptSet
from s1othello.stats import bootstrap_ci, mean, percentile, wilson
from s1othello.telemetry import append_jsonl

RUNS_DIR = Path("runs")


def _git_rev() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def new_run_dir(tag: str, mode: str) -> Path:
    d = RUNS_DIR / f"{tag}-{mode}-{time.strftime('%Y%m%d-%H%M%S')}"
    (d / "calls").mkdir(parents=True, exist_ok=False)
    return d


async def _close(*backends) -> None:
    for b in backends:
        for inner in (b, getattr(b, "model", None), getattr(b, "search", None)):
            if inner is not None and hasattr(inner, "aclose"):
                await inner.aclose()


def _decision_stats(views: list[dict]) -> dict:
    model = sum(v["model"] for v in views)
    fb = sum(v["fallback"] for v in views)
    lat = [x for v in views for x in v["latencies_ms"]]
    errors = [e for v in views for e in v["errors"]][:5]
    return {"decisions": model + fb, "forced": sum(v["forced"] for v in views), "fallback": fb,
            "fallback_rate": fb / (model + fb) if model + fb else None,
            "p50_latency_ms": percentile(lat, 50), "p95_latency_ms": percentile(lat, 95),
            "error_samples": errors}


def summarize_games(backend: str, opponent: str, views_by_opening: dict[int, list[dict]]) -> dict:
    views = [v for vs in views_by_opening.values() for v in vs]
    n = len(views)
    wins = sum(v["score"] == 1.0 for v in views)
    draws = sum(v["score"] == 0.5 for v in views)
    score_clusters = [[v["score"] for v in vs] for vs in views_by_opening.values()]
    diff_clusters = [[v["disc_diff"] for v in vs] for vs in views_by_opening.values()]
    return {"backend": backend, "opponent": opponent, "games": n, "openings": len(views_by_opening),
            "wins": wins, "draws": draws, "losses": n - wins - draws,
            "win_rate": wins / n if n else None, "win_rate_ci": wilson(wins, n),
            "score": mean([v["score"] for v in views]), "score_ci": bootstrap_ci(score_clusters),
            "disc_diff": mean([v["disc_diff"] for v in views]), "disc_diff_ci": bootstrap_ci(diff_clusters),
            **_decision_stats(views)}


async def _games(cfg: dict, run: Path) -> list[dict]:
    ps = PromptSet.load(cfg["prompt_version"])
    openings = make_openings(cfg["openings"], seed=cfg["seed"])
    opponent = make_backend(cfg["opponent"], seed=cfg["seed"])
    sem = asyncio.Semaphore(cfg["concurrency"])
    summaries = []
    for name in cfg["backends"]:
        be = make_backend(name, seed=cfg["seed"])
        calls = run / "calls" / f"{name}.jsonl"
        log = lambda row, _p=calls, _n=name: append_jsonl(_p, row) if row["backend"] == _n else None  # noqa: E731

        async def one(i: int, colour: str, _be=be, _log=log) -> tuple[int, dict]:
            async with sem:
                black, white = (_be, opponent) if colour == "B" else (opponent, _be)
                g = await play_game(black, white, ps, openings[i], log=_log, opening=i,
                                    prompt_version=ps.version)
            append_jsonl(run / "games.jsonl", {"backend": name, "opponent": cfg["opponent"],
                                               "backend_colour": colour, **g})
            return i, seat_view(g, colour)

        results = await asyncio.gather(*(one(i, c) for i in range(len(openings)) for c in "BW"))
        by_opening: dict[int, list[dict]] = {}
        for i, v in results:
            by_opening.setdefault(i, []).append(v)
        s = summarize_games(name, cfg["opponent"], by_opening)
        s["prompt_version"] = ps.version
        print(f"[{name} vs {cfg['opponent']}] score={s['score']:.3f} wins={s['wins']}/{s['games']} "
              f"disc_diff={s['disc_diff']:+.1f} fallback={_pct(s['fallback_rate'])} "
              f"p50={_ms(s['p50_latency_ms'])}", flush=True)
        summaries.append(s)
        await _close(be)
    await _close(opponent)
    return summaries


def summarize_regret(rows: list[dict]) -> dict:
    """rows: decisions.jsonl rows of one backend, each joined with its position."""
    def block(rs: list[dict]) -> dict:
        if not rs:
            return {"n": 0}
        best = sum(r["is_best"] for r in rs)
        reg = [r["regret"] for r in rs]
        rnd = sum(r["random_regret"] for r in rs)
        out = {"n": len(rs), "best_rate": best / len(rs), "best_rate_ci": wilson(best, len(rs)),
               "regret": mean(reg), "regret_ci": bootstrap_ci([[x] for x in reg]),
               "skill_vs_random": 1 - sum(reg) / rnd if rnd > 0 else None}
        lost = [r["outcome_lost"] for r in rs if "outcome_lost" in r]
        if lost:
            out["outcome_lost_rate"] = sum(lost) / len(lost)
        return out

    exact = [r for r in rows if r["exact"]]
    proxy = [r for r in rows if not r["exact"]]
    tags = sorted({t for r in rows for t in r["tags"]})
    lat = [r["latency_ms"] for r in rows if r["source"] != "forced"]
    fb = sum(r["source"] == "fallback" for r in rows)
    return {"exact": block(exact), "proxy": block(proxy),
            "phases": {p: block([r for r in rows if r["phase"] == p]) for p, _, _ in PHASES},
            "tags": {t: block([r for r in rows if t in r["tags"]]) for t in tags},
            "decisions": len(rows), "fallback": fb, "fallback_rate": fb / len(rows) if rows else None,
            "p50_latency_ms": percentile(lat, 50), "p95_latency_ms": percentile(lat, 95)}


async def _regret(cfg: dict, run: Path) -> list[dict]:
    ps = PromptSet.load(cfg["prompt_version"])
    meta, positions = load_set(Path(cfg["positions"]))
    if cfg.get("limit"):
        positions = positions[: cfg["limit"]]
    sem = asyncio.Semaphore(cfg["concurrency"])
    summaries = []
    for name in cfg["backends"]:
        be = make_backend(name, seed=cfg["seed"])

        async def one(row: dict, _be=be, _name=name) -> dict:
            board = tuple(row["board"])
            async with sem:
                d, legal, _, _ = await decide(_be, ps, board, row["player"])
            append_jsonl(run / "calls" / f"{_name}.jsonl",
                         call_row(_name, ps, d, board, row["player"], legal, position=row["id"]))
            rec = {"backend": _name, "position": row["id"], "phase": row["phase"], "tags": row["tags"],
                   "exact": row["exact"], "move": d.move, "source": d.source, "confidence": d.confidence,
                   "latency_ms": d.latency_ms, "prompt_version": ps.version, **regret_of(row, d.move)}
            append_jsonl(run / "decisions.jsonl", rec)
            return rec

        recs = await asyncio.gather(*(one(r) for r in positions))
        s = {"backend": name, "positions": cfg["positions"], "prompt_version": ps.version,
             **summarize_regret(recs)}
        e = s["exact"]
        print(f"[{name}] exact n={e['n']} best={_pct(e.get('best_rate'))} regret={_f(e.get('regret'))} discs "
              f"skill={_f(e.get('skill_vs_random'))} | proxy best={_pct(s['proxy'].get('best_rate'))} "
              f"| fallback={_pct(s['fallback_rate'])} p50={_ms(s['p50_latency_ms'])}", flush=True)
        summaries.append(s)
        await _close(be)
    return summaries


def run_eval(cfg: dict) -> Path:
    run = new_run_dir(cfg["tag"], cfg["mode"])
    cfg = {**cfg, "git_rev": _git_rev(), "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (run / "config.json").write_text(json.dumps(cfg, indent=2))
    runner = {"games": _games, "regret": _regret}[cfg["mode"]]
    summaries = asyncio.run(runner(cfg, run))
    (run / "summary.json").write_text(json.dumps({"config": cfg, "summaries": summaries}, indent=2, default=str))
    print(f"wrote {run}")
    return run


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.1%}"


def _f(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}"


def _ms(x: float | None) -> str:
    return "-" if x is None else f"{x:.0f}ms"
