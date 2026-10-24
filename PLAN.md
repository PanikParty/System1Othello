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
For a sampled position s with mover to move:
```
L(s) = V(s, a*) - V(s, a_model)
```
where `a*` is the solver's best move, `a_model` is the backend's chosen move, and `V` is the
solver's evaluation of the resulting position (exact disc differential once `empties(board) <=
EXACT_EMPTIES_THRESHOLD` (10), else a depth-limited negamax/alpha-beta static eval). Lower regret
is better; regret of exactly 0 means the backend matched the solver's best move for that position.
Positions are sampled by self-play rollouts of the **heuristic** backend only (see `_sample_positions`
in `cli.py`) -- never tuned on any model under test, satisfying Test D's "no training on the eval
set" requirement for the positions that feed Test B too.

Known limitation: depth-limited (non-exact) regret uses a static positional eval as a proxy, which
is itself imperfect away from the endgame -- flagged in the source discussion. `--depth` is exposed
so this can be tuned; raising it is pure cost (more nodes), not a protocol change.

### Test C -- Full games (`eval --mode games`)
Each backend under test plays `--episodes` full games against a fixed `--opponent` (default:
`minimax`), with colors alternated every other game to cancel the first-move advantage. Recorded
per game and aggregated per backend:
- win rate, disc differential (signed, from the tested backend's perspective)
- fallback rate (= (illegal choices + backend errors) / total moves) -- "Illegal move rate" /
  "reliability of the decision interface" from the source discussion
- p50 / p95 decision latency
- (cost per game: not yet wired -- needs per-backend $/call pricing, see §4 below)

Recommended first matrix (per the user's chosen initial scope): baselines (`heuristic`, `random`,
`minimax`) wired and validated first, then `jev`, `clef`, `clef-flash`, `laya-*`, `semif` pointed
at live endpoints.

### Test D -- Generalization to unfamiliar positions (not yet built)
The source discussion's most novel idea: sample held-out positions by bucket --
openings / midgame / contested-corner / few-legal-move / forced-pass / sparse-endgame -- and
confirm no backend was tuned on them. Planned shape: a frozen `positions/holdout_v1.jsonl` of
labeled (board, player, bucket) tuples, generated once (e.g. from solver vs. solver self-play at
varied depths + manual curation for the "forced pass" and "contested corner" buckets, which are
rare under random/heuristic self-play and need to be constructed directly), committed to the repo
so every future PR evaluates against the exact same frozen set. **Not implemented in v1** --
needs deliberate curation, not generated code, to avoid quietly building a biased set.

## §3. Confidence-gated hybrid search (not yet built)
The source discussion's hypothesis worth testing later: a System 1 model might be a mediocre
standalone player yet still valuable as a **move-ranking prior for alpha-beta**, or as a **router**
that only invokes the expensive `minimax` backend when its own confidence is low:
```
position -> backend.system_one() -> confidence = answers["move"].max_prob
    high confidence -> play backend's move directly
    low confidence  -> fall through to minimax (deeper, slower, but assumed-stronger)
```
This is a straightforward extension of `agent.decide`'s existing fallback mechanism (same shape,
different trigger: low confidence instead of error/illegal). Confidence must be *calibrated*
against observed regret first (Test B gives exactly that pairing: confidence vs. regret per
sample) before it's trustworthy as a routing signal -- per the source discussion's explicit
warning that "a model can be confidently wrong." Build order: (1) run Test B across backends,
(2) plot confidence vs. regret, (3) only then pick a confidence threshold and wire the router.

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
