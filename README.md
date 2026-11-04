# s1othello: System One models play Othello

A companion benchmark to [System1Doom](https://github.com/PanikParty/System1Doom), asking a
narrower question: **can a text-only System One decision model (Jev, Clef, Laya, SemIf, ...)
make strategically good judgments from a fully observable board, without searching a game tree?**

Othello is the control condition Doom can't be. It has a small action space, it is fully
observable and deterministic, and it is exactly solvable near the end. So every move can be
scored against a known-correct reference instead of a proxy heuristic.

> **Rule: code computes the geometry (legal moves, flips, terminal state); the model only
> ever judges between the legal options it is handed.** Same split as System1Doom's PLAN.md §0.

## Findings (details: [docs/results-m2.md](docs/results-m2.md))

1. **On a bare board, no model judges better than a square-weight table.** On 200 positions
   solved exactly (≤ 20 empties), Jev, Clef-Flash, SemIf and Laya are statistically tied
   with the `heuristic` table or worse. Laya is significantly worse. Jev picks an optimal
   move 26.5% of the time; uniform random picks one 25.5% of the time.
2. **Code-computed move facts (prompt v2) help, but a fixed rule over the same facts
   beats every model.** Jev v2 scores 0.575 against the heuristic (v1: 0.125); the `facts`
   rule scores 0.700, with less than two thirds of Jev v2's exact regret (4.96 vs 7.77 discs).
3. **Confidence carries no information beyond the number of legal moves.** For all models
   and both prompts, AUC(max_prob → optimal move) ≤ AUC(1/n_legal).
4. **Hybrids:** a confidence gate in front of minimax is worth what counting legal moves is
   worth. As a move prior for search, Jev's top 3 is no better than taking the first three
   moves in board order.

## Quick start
```bash
uv sync --extra dev
uv run pytest -q                      # 36 tests, no network; the C core compiles on first use

uv run s1othello play --black heuristic --white minimax-d2 --opening-seed 1
uv run s1othello play --black jev --white heuristic --prompt-version v2

# Test C: 20 seeded openings x both colours vs a fixed opponent
uv run s1othello eval --mode games --backends heuristic,facts,jev --opponent minimax-d2 \
  --openings 20 --prompt-version v2 --tag mytag

# Test B/D: regret against the oracle on the frozen 500-position set
uv run s1othello eval --mode regret --backends heuristic,jev --positions positions/v1.jsonl --tag mytag

# §3: confidence vs the 1/n_legal control, offline gate curve
uv run s1othello analyze --runs runs/*regret* --models jev@v1 --search minimax-d2@v1

uv run s1othello report               # runs/report.md (recomputed from decisions.jsonl)
```

Each eval writes `runs/<tag>-<mode>-<time>/` containing `config.json`, `games.jsonl` or
`decisions.jsonl`, `calls/<backend>.jsonl` (every decision, with `prompt_version`, its
probabilities and its source: `model` / `fallback` / `forced`), and `summary.json`.

Keys: Jev reads `TYPESAFE_API_KEY` or the file at `TYPESAFE_API_KEY_FILE` (default
`./Jev.key`). The Framework model servers need bearer tokens: on the Framework, run
`. scripts/framework_env.sh`. Any HTTP config's url can be overridden with `$<NAME>_URL`,
e.g. `CLEF_FLASH_URL=http://framework.local:8100` from the Mac.

## Backends
| name | what |
|---|---|
| `random` | Uniform over legal moves. The floor. |
| `greedy` | The move that flips the most discs. The naive "immediate reward" policy. |
| `heuristic` | Classic square-weight table, no lookahead. Fallback target. |
| `facts` | A fixed rule over exactly prompt v2's per-move facts. v2's control. |
| `minimax-d1/d2/d4/d6` | Native alpha-beta at that depth, exact in the last 14 empties. |
| `jev` | TypeSafe Jev (`/v1/systemone`). |
| `clef-flash`, `clef` | Clef-Flash 9B / Clef 27B (System1Doom's `serve_clef.py`), Framework :8100 / :8101. |
| `laya-framework` | Laya `laya-serve`, Framework :8000. |
| `semif` | SemIf Qwen3.5-4B, Framework :8010. Its server rejects more than 16 options. |
| `*-gate`, `*-prune3`, `*-coin40`, `*-count7/9` | §3 routers (`backends/router.py`): confidence gate, top-k prior for search, and the blind and move-count controls. |

## The tests
- **A, legal move selection:** implicit. Illegal or failed answers become labelled fallbacks.
  Positions with one legal move are `forced` and never sent.
- **B, move regret:** `positions/v1.jsonl`, 500 positions (5 phases × 100) from non-model
  self-play. They are solved exactly at ≤ 20 empties and by depth-10 search otherwise (the
  proxy, reported separately). Metrics: best-move rate, regret, skill against random,
  outcome-lost rate, and paired comparisons.
- **C, full games:** seeded, balanced random openings, each played with colours swapped.
  Score, disc differential, fallback rate, p50/p95 latency, bootstrap CIs over openings.
- **D, generalisation:** Test B broken down by phase (opening … final) and by tag (corner
  available, x-square legal, can force a pass, few moves, greedy trap, outcome critical).

Engine: `engine.py` (readable Python rules) plus `native/ob.c` (bitboards, exact solver,
midgame search), cross-checked against each other in the tests. See CLAUDE.md for verified
engine facts and PLAN.md for the design.

## Not done
- Clef 27B: OOM on load on the Framework while other workloads share its memory; rerun
  `scripts/campaign_clef27.sh` once ~57 GB is free (docs/results-m2.md, Caveats).
- A stronger midgame oracle (e.g. Edax) for the proxy positions. Building third-party code
  was not authorised during this work.
- Board-representation and prompt-wording ablations beyond v1/v2 (PLAN.md §4).
- Cost per game.
