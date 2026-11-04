"""s1othello CLI.

    s1othello play --black heuristic --white minimax-d2 [--opening-seed 3]
    s1othello eval --mode games --backends heuristic,jev --opponent minimax-d2 --openings 10 --tag m1
    s1othello eval --mode regret --backends heuristic,jev --positions positions/v1.jsonl --tag m1
    s1othello build-positions --out positions/v1.jsonl --per-phase 100 --workers 32
    s1othello report
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from s1othello.engine import Position


def cmd_play(args: argparse.Namespace) -> None:
    from s1othello.backends.factory import make_backend
    from s1othello.games import play_game
    from s1othello.openings import make_openings
    from s1othello.state import PromptSet

    ps = PromptSet.load(args.prompt_version)
    start = Position.start() if args.opening_seed is None else make_openings(1, seed=args.opening_seed)[0]

    async def go() -> dict:
        black, white = make_backend(args.black, seed=args.seed), make_backend(args.white, seed=args.seed)
        try:
            return await play_game(black, white, ps, start, verbose=True)
        finally:
            for b in (black, white):
                if hasattr(b, "aclose"):
                    await b.aclose()

    g = asyncio.run(go())
    print(f"\nResult: B({args.black}) {g['black_discs']} - W({args.white}) {g['white_discs']}  "
          f"winner={g['winner'] or 'draw'}  plies={g['plies']}  "
          f"fallback B={g['B']['fallback']} W={g['W']['fallback']}")


def cmd_eval(args: argparse.Namespace) -> None:
    from s1othello.evaluate import run_eval

    cfg = {"mode": args.mode, "tag": args.tag, "backends": args.backends.split(","), "seed": args.seed,
           "prompt_version": args.prompt_version, "concurrency": args.concurrency}
    if args.mode == "games":
        cfg.update(opponent=args.opponent, openings=args.openings)
    else:
        cfg.update(positions=args.positions, limit=args.limit)
    run_eval(cfg)


def cmd_build_positions(args: argparse.Namespace) -> None:
    import time

    from s1othello.positions import build_set, save_set

    t0 = time.time()
    rows = build_set(args.per_phase, args.seed, depth=args.depth, exact_empties=args.exact_empties,
                     workers=args.workers, n_games=args.games)
    meta = {"seed": args.seed, "per_phase": args.per_phase, "depth": args.depth,
            "exact_empties": args.exact_empties, "pool_games": args.games, "n": len(rows),
            "built": time.strftime("%Y-%m-%dT%H:%M:%S"), "build_s": round(time.time() - t0)}
    save_set(rows, Path(args.out), meta)
    print(f"wrote {args.out}: {len(rows)} positions in {meta['build_s']} s")


def cmd_analyze(args: argparse.Namespace) -> None:
    import json

    from s1othello.analysis import calibration, gate_curve, load_decisions, pareto, random_gate

    dec = load_decisions([Path(r) for r in args.runs])
    search = dec[args.search]
    out = {}
    for name in args.models.split(","):
        model = dec[name]
        cal = calibration(list(model.values()))
        curve = gate_curve(model, search)
        front = pareto(curve)
        out[name] = {"calibration": cal, "gate_pareto": front}
        auc_s = "-" if cal["auc_best"] is None else f"{cal['auc_best']:.3f}"
        print(f"== {name} (search: {args.search}) n={cal['n']} AUC(conf -> best move)={auc_s}")
        for b in cal["bins"]:
            print(f"   conf~{b['conf_mean']:.2f}  best={b['best_rate']:.1%}  n={b['n']}")
        print("   gate: threshold  search_share  best_rate  (random routing at same share)  regret")
        for c in front:
            print(f"         {c['threshold']:.3f}      {c['search_share']:.1%}       {c['best_rate']:.1%}"
                  f"      ({random_gate(model, search, c['search_share']):.1%})"
                  f"                {c['regret']:.2f}")
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2))
        print(f"wrote {args.out}")


def cmd_report(args: argparse.Namespace) -> None:
    from s1othello.report import build_report

    runs = Path(args.runs)
    text = build_report(runs, args.tag)
    out = Path(args.out) if args.out else runs / "report.md"
    out.write_text(text)
    print(text)
    print(f"wrote {out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="s1othello")
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("play", help="one verbose game")
    pp.add_argument("--black", required=True)
    pp.add_argument("--white", required=True)
    pp.add_argument("--opening-seed", type=int, default=None, help="start from a seeded random opening")
    pp.add_argument("--prompt-version", default="v1")
    pp.add_argument("--seed", type=int, default=None)
    pp.set_defaults(func=cmd_play)

    pe = sub.add_parser("eval", help="Test C (games) or Test B/D (regret)")
    pe.add_argument("--mode", choices=["games", "regret"], required=True)
    pe.add_argument("--backends", required=True, help="comma-separated backend names")
    pe.add_argument("--tag", default="adhoc")
    pe.add_argument("--opponent", default="minimax-d2", help="games: the fixed opponent")
    pe.add_argument("--openings", type=int, default=10, help="games: openings, each played with both colours")
    pe.add_argument("--positions", default="positions/v1.jsonl", help="regret: frozen position set")
    pe.add_argument("--limit", type=int, default=None, help="regret: only the first N positions")
    pe.add_argument("--prompt-version", default="v1")
    pe.add_argument("--concurrency", type=int, default=1)
    pe.add_argument("--seed", type=int, default=1234)
    pe.set_defaults(func=cmd_eval)

    pb = sub.add_parser("build-positions", help="generate + solve a frozen Test B/D position set")
    pb.add_argument("--out", default="positions/v1.jsonl")
    pb.add_argument("--per-phase", type=int, default=100)
    pb.add_argument("--depth", type=int, default=10)
    pb.add_argument("--exact-empties", type=int, default=20)
    pb.add_argument("--games", type=int, default=4000, help="self-play games in the candidate pool")
    pb.add_argument("--workers", type=int, default=1)
    pb.add_argument("--seed", type=int, default=20261103)
    pb.set_defaults(func=cmd_build_positions)

    pa = sub.add_parser("analyze", help="§3: confidence calibration + offline gate-router curve")
    pa.add_argument("--runs", nargs="+", required=True, help="regret run dirs to pool")
    pa.add_argument("--models", required=True, help="comma-separated backend@prompt keys, e.g. jev@v1")
    pa.add_argument("--search", default="minimax-d2@v1", help="search backend@prompt to route to")
    pa.add_argument("--out", default=None)
    pa.set_defaults(func=cmd_analyze)

    pr = sub.add_parser("report", help="aggregate runs/*/summary.json into runs/report.md")
    pr.add_argument("--runs", default="runs")
    pr.add_argument("--tag", default=None, help="only runs whose tag starts with this")
    pr.add_argument("--out", default=None)
    pr.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
