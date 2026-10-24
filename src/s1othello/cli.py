"""s1othello CLI: play, eval, report.

    s1othello play --black jev --white minimax
    s1othello eval --mode games --backends jev,clef,laya-framework,heuristic,random --opponent minimax --episodes 20 --seed 1234
    s1othello eval --mode regret --backends jev,clef --positions 200 --seed 1234 --depth 6
    s1othello report
"""
from __future__ import annotations

import argparse
import asyncio
import random as pyrandom
import sys
import time
from pathlib import Path

from s1othello.backends.factory import make_backend
from s1othello.agent import decide
from s1othello.engine import Position, disc_counts, other
from s1othello.metrics import EvalSummary, move_regret
from s1othello.telemetry import append_jsonl

RUNS_DIR = Path("runs")


async def play_game(backend_black, backend_white, verbose: bool = False) -> dict:
    pos = Position.start()
    plies = 0
    fb_black = fb_white = 0
    lat_black, lat_white = [], []
    while not pos.is_terminal():
        backend = backend_black if pos.to_move == "B" else backend_white
        d = await decide(backend, pos.board, pos.to_move)
        if pos.to_move == "B":
            lat_black.append(d.latency_ms)
            fb_black += int(d.used_fallback)
        else:
            lat_white.append(d.latency_ms)
            fb_white += int(d.used_fallback)
        if verbose:
            print(f"  ply {plies:>3} {pos.to_move} -> {d.move}"
                  f"{' (fallback)' if d.used_fallback else ''}")
        pos = pos.step(d.move)
        plies += 1
    b, w = disc_counts(pos.board)
    winner = "B" if b > w else ("W" if w > b else None)
    return {
        "black_discs": b, "white_discs": w, "winner": winner, "plies": plies,
        "fallback_black": fb_black, "fallback_white": fb_white,
        "avg_latency_ms_black": sum(lat_black) / len(lat_black) if lat_black else 0.0,
        "avg_latency_ms_white": sum(lat_white) / len(lat_white) if lat_white else 0.0,
        "moves_black": len(lat_black), "moves_white": len(lat_white),
    }


def cmd_play(args: argparse.Namespace) -> None:
    black = make_backend(args.black, seed=args.seed)
    white = make_backend(args.white, seed=args.seed)
    result = asyncio.run(play_game(black, white, verbose=True))
    print(f"\nResult: B {result['black_discs']} - W {result['white_discs']}  "
          f"winner={result['winner'] or 'draw'}  plies={result['plies']}")


def cmd_eval(args: argparse.Namespace) -> None:
    backends = args.backends.split(",")
    run_id = time.strftime("%Y-%m-%d_%H%M%S")
    out_path = RUNS_DIR / f"{run_id}_{args.mode}.jsonl"

    if args.mode == "games":
        opponent = make_backend(args.opponent, seed=args.seed)
        for name in backends:
            summary = EvalSummary(backend=name)
            for i in range(args.episodes):
                be = make_backend(name, seed=(args.seed or 0) + i)
                # alternate colors to cancel first-move advantage
                if i % 2 == 0:
                    r = asyncio.run(play_game(be, opponent))
                    mine, theirs = r["black_discs"], r["white_discs"]
                    fb, moves = r["fallback_black"], r["moves_black"]
                    lat = r["avg_latency_ms_black"]
                    won = r["winner"] == "B"
                    drew = r["winner"] is None
                else:
                    r = asyncio.run(play_game(opponent, be))
                    mine, theirs = r["white_discs"], r["black_discs"]
                    fb, moves = r["fallback_white"], r["moves_white"]
                    lat = r["avg_latency_ms_white"]
                    won = r["winner"] == "W"
                    drew = r["winner"] is None
                summary.games += 1
                summary.wins += int(won)
                summary.draws += int(drew)
                summary.losses += int(not won and not drew)
                summary.disc_diff_sum += mine - theirs
                summary.fallback_count += fb
                summary.move_count += moves
                summary.latencies_ms.append(lat)
                append_jsonl(out_path, {"backend": name, "episode": i, **r})
                print(f"[{name}] game {i}: {mine}-{theirs} "
                      f"{'W' if won else ('D' if drew else 'L')} fallback={fb}/{moves}")
            _print_summary(summary)
            append_jsonl(out_path, {"summary": True, "backend": name,
                                     "win_rate": summary.win_rate, "fallback_rate": summary.fallback_rate,
                                     "disc_diff_avg": summary.disc_diff_sum / summary.games,
                                     "p50_latency_ms": summary.p50_latency_ms,
                                     "p95_latency_ms": summary.p95_latency_ms})

    elif args.mode == "regret":
        positions = _sample_positions(args.positions, args.seed or 0)
        for name in backends:
            summary = EvalSummary(backend=name)
            be = make_backend(name, seed=args.seed)
            for board, player in positions:
                d = asyncio.run(decide(be, board, player))
                sample = move_regret(board, player, d.move, depth=args.depth)
                summary.regrets.append(sample.regret)
                summary.latencies_ms.append(d.latency_ms)
                summary.fallback_count += int(d.used_fallback)
                summary.move_count += 1
                append_jsonl(out_path, {"backend": name, "regret": sample.regret,
                                        "is_best": sample.is_best, "fallback": d.used_fallback,
                                        "latency_ms": d.latency_ms})
            print(f"[{name}] avg_regret={summary.avg_regret:.2f}  "
                  f"fallback_rate={summary.fallback_rate:.1%}  n={summary.move_count}")
    else:
        raise SystemExit(f"unknown mode {args.mode!r}")
    print(f"\nwrote {out_path}")


def _print_summary(s: EvalSummary) -> None:
    print(f"  == {s.backend}: win_rate={s.win_rate:.1%} draws={s.draws} "
          f"avg_disc_diff={s.disc_diff_sum / s.games:+.1f} "
          f"fallback_rate={s.fallback_rate:.1%} "
          f"p50={s.p50_latency_ms:.0f}ms p95={s.p95_latency_ms:.0f}ms")


def _sample_positions(n: int, seed: int) -> list[tuple]:
    """Random legal-play rollouts, sampled at a random ply, for Test B/D.
    Not tuned on any model -- pure self-play by the heuristic backend."""
    rng = pyrandom.Random(seed)
    positions = []
    from s1othello.backends.heuristic import HeuristicBackend
    heur = HeuristicBackend()
    while len(positions) < n:
        pos = Position.start()
        trace = [(pos.board, pos.to_move)]
        while not pos.is_terminal():
            d = asyncio.run(decide(heur, pos.board, pos.to_move))
            pos = pos.step(d.move)
            trace.append((pos.board, pos.to_move))
        if len(trace) > 4:
            board, player = trace[rng.randint(2, len(trace) - 2)]
            if not Position(board, player).is_terminal():
                positions.append((board, player))
    return positions[:n]


def cmd_report(args: argparse.Namespace) -> None:
    from s1othello.telemetry import read_jsonl

    files = sorted(RUNS_DIR.glob("*.jsonl"))
    if not files:
        print("no runs found under runs/")
        return
    lines = ["# s1othello report\n", "| run | backend | metric | value |", "|---|---|---|---|"]
    for f in files:
        for rec in read_jsonl(f):
            if rec.get("summary"):
                for k in ("win_rate", "fallback_rate", "disc_diff_avg", "p50_latency_ms", "p95_latency_ms"):
                    if k in rec and rec[k] is not None:
                        lines.append(f"| {f.stem} | {rec['backend']} | {k} | {rec[k]:.3f} |")
    report_path = RUNS_DIR / "report.md"
    report_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {report_path}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="s1othello")
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("play", help="one game, verbose move log")
    pp.add_argument("--black", required=True)
    pp.add_argument("--white", required=True)
    pp.add_argument("--seed", type=int, default=None)
    pp.set_defaults(func=cmd_play)

    pe = sub.add_parser("eval", help="batch eval: games or regret")
    pe.add_argument("--mode", choices=["games", "regret"], required=True)
    pe.add_argument("--backends", required=True, help="comma-separated backend names")
    pe.add_argument("--opponent", default="minimax", help="games mode: fixed opponent")
    pe.add_argument("--episodes", type=int, default=20)
    pe.add_argument("--positions", type=int, default=200, help="regret mode: #sampled positions")
    pe.add_argument("--depth", type=int, default=6, help="regret mode: solver search depth")
    pe.add_argument("--seed", type=int, default=1234)
    pe.set_defaults(func=cmd_eval)

    pr = sub.add_parser("report", help="aggregate runs/*.jsonl into runs/report.md")
    pr.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
