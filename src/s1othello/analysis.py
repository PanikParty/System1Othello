"""PLAN.md §3 step (2): confidence vs regret, and an offline simulation of the gate router.

Uses only Test B decisions.jsonl rows (no new model calls). For a model backend M and a
search backend S evaluated on the same frozen positions:
- calibration: AUC of M's confidence for "chose an optimal move", and reliability bins;
- gate curve: for each threshold t, play M's move when confidence >= t else S's move,
  and report the share sent to S with the resulting best-move rate and mean regret.
Forced and fallback decisions carry no confidence; a fallback counts as "send to search".
"""
from __future__ import annotations

import json
from pathlib import Path

from s1othello.stats import mean


def load_decisions(run_dirs: list[Path]) -> dict[str, dict[str, dict]]:
    """{backend: {position_id: row}} over the given regret runs (later runs win)."""
    out: dict[str, dict[str, dict]] = {}
    for d in run_dirs:
        for line in (Path(d) / "decisions.jsonl").read_text().splitlines():
            r = json.loads(line)
            out.setdefault(f"{r['backend']}@{r['prompt_version']}", {})[r["position"]] = r
    return out


def auc(scores: list[float], labels: list[bool]) -> float | None:
    """P(score of a random positive > score of a random negative), ties count half."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    ranked = sorted((s, y) for s, y in zip(scores, labels))
    # midranks for ties
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        mid = (i + j + 1) / 2
        rank_sum += mid * sum(1 for k in range(i, j) if ranked[k][1])
        i = j
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def calibration(rows: list[dict], n_bins: int = 5) -> dict:
    rs = [r for r in rows if r["confidence"] is not None]
    conf = [r["confidence"] for r in rs]
    best = [bool(r["is_best"]) for r in rs]
    bins = []
    if rs:
        order = sorted(range(len(rs)), key=lambda i: conf[i])
        size = max(1, len(rs) // n_bins)
        for b in range(0, len(rs), size):
            idx = order[b:b + size]
            bins.append({"conf_mean": mean([conf[i] for i in idx]), "best_rate": mean([best[i] for i in idx]),
                         "n": len(idx)})
    return {"n": len(rs), "auc_best": auc(conf, best),
            "auc_best_exact": auc([r["confidence"] for r in rs if r["exact"]],
                                  [bool(r["is_best"]) for r in rs if r["exact"]]),
            "bins": bins}


def gate_curve(model: dict[str, dict], search: dict[str, dict], exact_only: bool = False) -> list[dict]:
    ids = [p for p in model if p in search and (model[p]["exact"] or not exact_only)
           and model[p]["source"] != "forced"]
    confs = sorted({model[p]["confidence"] for p in ids if model[p]["confidence"] is not None})
    thresholds = [0.0] + confs + [1.01]
    curve = []
    for t in thresholds:
        chosen = []
        routed = 0
        for p in ids:
            m = model[p]
            if m["confidence"] is None or m["confidence"] < t:
                chosen.append(search[p])
                routed += 1
            else:
                chosen.append(m)
        curve.append({"threshold": t, "search_share": routed / len(ids) if ids else None,
                      "best_rate": mean([bool(c["is_best"]) for c in chosen]),
                      "regret": mean([c["regret"] for c in chosen])})
    return curve


def pareto(curve: list[dict]) -> list[dict]:
    """Thresholds not dominated on (lower search_share, higher best_rate)."""
    pts = sorted(curve, key=lambda c: (c["search_share"], -c["best_rate"]))
    out, best = [], -1.0
    for c in pts:
        if c["best_rate"] > best:
            out.append(c)
            best = c["best_rate"]
    return out


def random_gate(model: dict[str, dict], search: dict[str, dict], share: float) -> float:
    """Best-move rate if the same share of positions went to search uniformly at random."""
    ids = [p for p in model if p in search and model[p]["source"] != "forced"]
    m = mean([bool(model[p]["is_best"]) for p in ids])
    s = mean([bool(search[p]["is_best"]) for p in ids])
    return (1 - share) * m + share * s
