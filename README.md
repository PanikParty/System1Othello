# s1othello: System One models play Othello

A companion benchmark to [System1Doom](https://github.com/PanikParty/System1Doom), asking a
narrower question: **can a text-only System One decision model (Jev, Clef, Laya, SemIf, ...) make
strategically good judgments from a fully-observable board state, without searching a game tree?**

Othello (Reversi) is the control condition Doom can't be: finite action space (<=~20 legal moves,
usually fewer), perfectly observable, deterministic, and solvable near the endgame -- so every move
can be scored against a known-correct reference instead of only a proxy heuristic.

> **Rule: code computes the geometry (legal moves, flips, terminal state); the model only ever
> judges between the legal options it is handed.** Same split as System1Doom's PLAN.md §0.

See `PLAN.md` for the full design (derived from the attached research discussion on why Othello is
a good companion benchmark, and the A→D test ladder below).

## Quick start
```bash
uv sync
uv run pytest -q

uv run s1othello play --black heuristic --white minimax
uv run s1othello play --black jev --white minimax

# Test C: full games vs a fixed opponent, alternating colors
uv run s1othello eval --mode games --backends heuristic,random,jev,clef-flash,laya-framework \
  --opponent minimax --episodes 20 --seed 1234

# Test B: move regret against the exact/near-exact solver on sampled positions
uv run s1othello eval --mode regret --backends jev,clef-flash,laya-framework \
  --positions 200 --depth 6 --seed 1234

uv run s1othello report   # runs/report.md
```

Jev reads `TYPESAFE_API_KEY` or a key file at `TYPESAFE_API_KEY_FILE` (default `./Jev.key`, gitignored).
Clef/Clef-Flash/Laya/SemIf are Jev-compatible `/v1/systemone` HTTP servers -- point
`configs/backends/<name>.yaml` at wherever you're serving them (reuses System1Doom's
`scripts/serve_clef.py`, `laya-serve`, SemIf's own server unmodified; zero new client code, same
`SystemOneHTTP` class).

## Backends
| name | transport | notes |
|---|---|---|
| `heuristic` | Python | Corner/edge/mobility weights, no search. Baseline, fallback target, label source. |
| `random` | Python | Uniform over legal moves. Fallback disabled so it stays a true floor. |
| `minimax` | Python (in-proc) | Negamax + alpha-beta, exact solve inside the last 10 empty squares. The search-engine reference. |
| `jev` | HTTP `/v1/systemone` | TypeSafe Jev. |
| `clef` / `clef-flash` | HTTP `/v1/systemone` | Cloudflare Clef 27B / Clef-Flash 9B. |
| `laya-http`-kind configs | HTTP `/v1/systemone` | Open-weight Laya, served however System1Doom already serves it. |
| `semif` | HTTP `/v1/systemone` | [SemIf](https://github.com/TheoLeeCJ/SemIf-OpenJev), Qwen3.5-4B typed-option logits. |
| any `systemone-http` kind | HTTP `/v1/systemone` | Point a new `configs/backends/<name>.yaml` at any Jev-compatible server. |

## The four tests (see PLAN.md for full detail)
- **A -- Legal move selection.** Sanity check only; even `random` passes.
- **B -- Move regret.** `L(s) = V(s,a*) - V(s,a_model)` against the solver's evaluation of every legal
  move. Lower is better. Run with `eval --mode regret`.
- **C -- Full games.** Win rate, disc differential, fallback (illegal-choice/error) rate, p50/p95
  latency, vs a fixed opponent, colors alternated to cancel first-move advantage. Run with
  `eval --mode games`.
- **D -- Generalization.** (Not yet wired -- see PLAN.md "Not yet built.") Held-out position buckets
  (openings / midgame / contested corners / forced passes / few-move endgames), never tuned on by
  any backend.

## Status
v1: engine, exact-near-endgame solver, heuristic/random/minimax baselines, Test B (regret) and
Test C (full games) harnesses, full `/v1/systemone` backend plumbing for Jev/Clef/Laya/SemIf ready
to point at live endpoints. Confidence-gated hybrid search (System 1 ranks candidates for
alpha-beta) and Test D's curated generalization set are designed in PLAN.md but not yet built.
