"""Aggregate runs/*/summary.json into runs/report.md."""
from __future__ import annotations

import json
from pathlib import Path

from s1othello.positions import PHASES
from s1othello.stats import bootstrap_ci, mean


def _ci(ci, fmt="{:.2f}") -> str:
    return "" if not ci else f" [{fmt.format(ci[0])}, {fmt.format(ci[1])}]"


def _p(x) -> str:
    return "-" if x is None else f"{x:.1%}"


def _ms(x) -> str:
    return "-" if x is None else f"{x:.0f}"


def _paired(runs_dir: Path, run_names: list[str], ref: str = "heuristic@v1") -> list[str]:
    """Exact-position regret of each backend minus `ref`'s, on positions both answered
    themselves (fallbacks dropped), with a bootstrap CI over positions."""
    dec: dict[str, dict[str, dict]] = {}
    for run in run_names:
        for line in (runs_dir / run / "decisions.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r["exact"] and r["source"] == "model":
                dec.setdefault(f"{r['backend']}@{r['prompt_version']}", {})[r["position"]] = r
    if ref not in dec:
        return []
    out = [f"### Paired: exact regret minus {ref.split('@')[0]}'s (discs; < 0 = better)", "",
           "| backend | prompt | n | mean diff | 95% CI |", "|---|---|---|---|---|"]
    for key in sorted(dec):
        if key == ref:
            continue
        common = [p for p in dec[key] if p in dec[ref]]
        diffs = [dec[key][p]["regret"] - dec[ref][p]["regret"] for p in common]
        name, pv = key.split("@")
        out.append(f"| {name} | {pv} | {len(common)} | {mean(diffs):+.2f} |{_ci(bootstrap_ci([[d] for d in diffs]), '{:+.2f}')} |")
    return out + [""]


def build_report(runs_dir: Path, tag_filter: str | None = None) -> str:
    games, regret = [], []
    for f in sorted(runs_dir.glob("*/summary.json")):
        d = json.loads(f.read_text())
        cfg = d["config"]
        if tag_filter and not cfg["tag"].startswith(tag_filter):
            continue
        for s in d["summaries"]:
            (games if cfg["mode"] == "games" else regret).append((f.parent.name, s))
    out = ["# s1othello report", ""]
    if games:
        out += ["## Test C: full games (paired openings, colours swapped)", "",
                "score = mean of win 1 / draw 0.5 / loss 0; CIs are 95% bootstrap over openings.", "",
                "| backend | prompt | opponent | games | score | W-D-L | disc diff | fallback | p50 / p95 ms | run |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for run, s in games:
            out.append(f"| {s['backend']} | {s.get('prompt_version', '-')} | {s['opponent']} | {s['games']} | "
                       f"{s['score']:.3f}{_ci(s['score_ci'])} | {s['wins']}-{s['draws']}-{s['losses']} | "
                       f"{s['disc_diff']:+.1f}{_ci(s['disc_diff_ci'], '{:+.1f}')} | {_p(s['fallback_rate'])} | "
                       f"{_ms(s['p50_latency_ms'])} / {_ms(s['p95_latency_ms'])} | {run} |")
        out.append("")
    if regret:
        out += ["## Test B: move regret against the oracle", "",
                "exact = positions with <= 20 empties, regret in final discs under perfect play. "
                "proxy = earlier positions, depth-10 search in eval points. best = chose an optimal move. "
                "skill = 1 - regret / regret of a uniform random move.", "",
                "| backend | prompt | exact n | exact best | exact regret (discs) | exact skill | outcome lost | "
                "proxy best | proxy skill | fallback | p50 ms | run |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for run, s in regret:
            e, p = s["exact"], s["proxy"]
            out.append(f"| {s['backend']} | {s['prompt_version']} | {e['n']} | {_p(e.get('best_rate'))} | "
                       f"{e.get('regret', 0):.2f}{_ci(e.get('regret_ci'))} | {e.get('skill_vs_random') or 0:.2f} | "
                       f"{_p(e.get('outcome_lost_rate'))} | {_p(p.get('best_rate'))} | "
                       f"{p.get('skill_vs_random') or 0:.2f} | {_p(s['fallback_rate'])} | "
                       f"{_ms(s['p50_latency_ms'])} | {run} |")
        out += ["", "### Test D: best-move rate by phase and tag", ""]
        cols = [p for p, _, _ in PHASES]
        tags = sorted({t for _, s in regret for t in s["tags"]})
        out += ["| backend | prompt | " + " | ".join(cols + tags) + " |",
                "|---|---|" + "---|" * (len(cols) + len(tags))]
        for _, s in regret:
            cells = [_p(s["phases"][c].get("best_rate")) for c in cols]
            cells += [_p(s["tags"].get(t, {}).get("best_rate")) for t in tags]
            out.append(f"| {s['backend']} | {s['prompt_version']} | " + " | ".join(cells) + " |")
        out.append("")
        out += _paired(runs_dir, sorted({run for run, _ in regret}))
    return "\n".join(out) + "\n"
