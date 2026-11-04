# PLAN.md -- s1othello design

Source concept: a research discussion on why Othello is a strong companion benchmark to
System1Doom for evaluating "System 1" text-only decision models (Jev, OpenAI Decisions API,
Clef, Laya, SemIf). Full transcript: https://chatgpt.com/s/t_6adc4dfb85b0819194d6cdac228fdcf8

## §0. The split (inherited from System1Doom, unchanged)
**Code computes the geometry. The model makes the judgment.**
The engine (this repo's `engine.py`) owns legal-move generation, flip resolution, and terminal
detection -- all deterministic and auditable. The model is only ever asked to pick one option from
a list of currently-legal moves (`state.py`'s `questions["move"]["criteria"]`). It never has to
reason about rule legality, only about which legal move is strategically best.

## §1. Why Othello over (or alongside) Doom
Doom tests perception + real-time control + judgment all at once, and its "ground truth" is fuzzy
(there is no oracle for "the objectively correct tactic"). Othello isolates judgment:
- Finite action space: <=20ish legal moves, often far fewer.
- Fully observable: the whole board is the whole state, no partial information, no perception step.
- Deterministic: given state + legal move, the resulting state is exact.
- Clear objective: more discs of your color at the end.
- A known-correct oracle near the endgame: exact minimax solve is tractable in the last ~10 empty
  squares, so "the single best move" is a verifiable fact, not an estimate.
- A real split between immediate reward and long-term value (flipping the most discs now can be
  strategically worse than a move that secures a corner), which is exactly the kind of judgment a
  System 1 model is supposed to be good at vs. naive greedy heuristics.

## §2. The four-test ladder
### Test A -- Legal move selection
Sanity/integration check: given state + legal moves, does the backend return one of them,
repeatably, within a reasonable latency? Even `random` passes this. Implemented implicitly by
`agent.decide`'s fallback-on-illegal-choice path; not a standalone CLI command because it adds no
signal beyond Test B/C's instrumentation (which already counts `fallback_rate`).

### Test B -- Move regret (`eval --mode regret`)
For a position s with the mover to move:
```
L(s) = V(s, a*) - V(s, a_model)
```
`V` is the oracle's value of each legal move, precomputed once and frozen with the position
set (`positions/v1.jsonl`, built by `build-positions`, C core in `native/ob.c`):
- **exact** when `empties <= 20`: the final disc differential under perfect play;
- **proxy** otherwise: depth-10 alpha-beta over a static eval in "eval points" (corners,
  squares next to empty corners, mobility, frontier). It is deliberately not the heuristic
  backend's square table, and values are clamped to +-200 when scoring regret.
Exact and proxy results are always reported separately (they are in different units).
Besides mean regret: best-move rate (chose an optimal move), skill = 1 - regret / regret of
a uniform random move, and outcome-lost rate (exact: a move that worsens the game result).
Quality is scored on the backend's own answers only; fallbacks are counted separately.

### Test C -- Full games (`eval --mode games`)
Every non-model backend is deterministic, so games start from `openings.make_openings`:
seeded random 6-ply openings, kept only if a depth-8 search scores them within +-20
points, each played twice with colours swapped (a paired design; CIs bootstrap over
openings). Recorded per game: score (win 1, draw 0.5), disc differential, fallback rate,
forced moves (one legal move: no call), p50/p95 per-decision latency. Opponents form a
ladder: `random < greedy ~ heuristic < minimax-d1 < minimax-d2 < minimax-d4`.

### Test D -- Generalization to unfamiliar positions (built as Test B's strata)
`positions/v1.jsonl` is stratified 5 x 100 by phase (opening 45-56 empties, midgame
30-44, late 21-29, endgame 15-20, final 1-14) and tagged corner_available,
x_square_legal, can_force_pass, few_moves, greedy_trap, outcome_critical. Positions come
from self-play by non-model policies only (random, greedy, heuristic, minimax-d1/d2 with
epsilon-random moves), so no backend under test was tuned on them. The set is committed
and never regenerated in place; a new set gets a new file name. The report shows
best-move rate per phase and tag. Hand-curated buckets remain possible future work.

### Prompt versions
`prompts/v1`: rules and bare move options. `prompts/v2`: v1 plus per-move facts the code
computes (flips, square kind, opponent replies, opponent gets a corner, opponent passes).
The `facts` backend is v2's control: a fixed rule over exactly those facts.

## §3. Confidence-gated hybrid search (built: `backends/router.py`, `analyze`)
Router modes: `gate` (model below a max_prob threshold -> minimax decides), `prune`
(minimax searches only the model's top-k), and two controls for `gate`: `coin` (a random
share goes to search) and `count` (search when >= N legal moves). `analyze` gives the
calibration step offline from Test B decisions: AUC of confidence for "best move" next to
the AUC of the trivial predictor 1/n_legal (max_prob rises mechanically with fewer
options, and those positions are easier), plus the simulated gate curve against random
and move-counting routing at the same search share.

## §4. Known gaps / explicitly deferred
- **Cost per game** -- needs a $/1k-tokens table per backend; `DecisionResult.usage` already
  carries `input_tokens` when a backend reports it, just not priced or aggregated yet.
- **Equal-compute vs. equal-cost reporting** -- source discussion flags this as a fairness
  requirement once more than one paid backend is compared; not needed while `heuristic`/`random`/
  `minimax` are the only wired baselines.
- **Board representation ablation** -- the source discussion suggests testing whether a structured
  array representation changes results vs. the current compact row-string format. Low priority
  until the row-string format is shown to be a bottleneck.
- **Image-based input** -- explicitly out of scope per the source discussion ("avoid sending a
  screenshot initially... visual perception would introduce an unnecessary variable").
