# Results M2/M3: System One models on Othello (2026-11-03/04)

Every number here comes from `runs/` (gitignored). Each table names its run ids, and
`uv run s1othello report` regenerates them. Code: commits c9bdfca (M1), 594288d (position
set), 72febf9 (M3), and the commit that adds this file.

**Setup.** Jev was called from the Mac (TypeSafe API). Laya (`laya-serve`, :8000), SemIf
(:8010) and Clef-Flash 9B (:8100) ran on the Framework Desktop (Strix Halo), one model
at a time. Clef 27B (:8101) ran on 2026-11-04 after a BIOS change to a 96 GB GPU carve-out
(see Caveats). It ran the v1 and v2 regret sets and v2 games only. Every backend got the same 20 openings (seed 1234) and the
same 500 frozen positions (`positions/v1.jsonl`). Prompt v1 has the rules and bare moves;
v2 adds per-move facts computed by the code (`prompts/v2/questions.yaml`). All five models
returned the same answer for a repeated input (deterministic), and every fallback is
labelled. The only interface failure was SemIf's server, which rejects questions with more
than 16 options (HTTP 422). That hit 11 of 500 Test B positions (2.2%) and 0.3% of its v2
game decisions.

## Headline

1. **On a bare board (v1) no System One model judges better than a square-weight table.**
   On positions with ≤ 20 empty squares, where the oracle is exact, every model's regret is
   statistically tied with the `heuristic` table or worse. Laya is worse than the table,
   and its point estimate is also worse than uniform random. Jev's best-move rate (26.5%)
   equals random's (25.5%). Clef 27B v1 (31.5%, 8.02 discs) is tied with the table.
2. **Facts computed by the code help, but a fixed rule over the same facts beats every
   model.** v2 lifts Jev from 0.125 to 0.575 against the heuristic, and Laya from 0.21 to
   0.43. The `facts` baseline (a hand-written rule over exactly v2's facts) scores 0.700,
   with exact regret 4.96 discs against Jev v2's 7.77. Clef 27B v2 is the strongest model and
   the only one significantly better than the heuristic (6.70 discs, paired −1.44 [−2.75, −0.01]).
   The facts rule still beats it (paired +1.74 [+0.58, +3.02] discs in the rule's favour), and
   in games it scores 0.487 against the heuristic, below Jev v2.
3. **Confidence carries little or no information beyond the number of legal moves.** For
   every model but Clef 27B, the AUC of max_prob for "picked an optimal move" is at most the
   AUC of the trivial predictor 1/n_legal, and the lift over uniform (max_prob × n_legal)
   has an AUC below 0.5, i.e. worse than chance. Clef 27B is the one exception and it is
   small: v2 0.698 vs 0.661, with lift AUC 0.48 (v1: 0.514). A simulated gate built on it is
   still within 0.5 points of routing the same share at random.
4. **The hybrids confirm it in play.** A confidence gate in front of minimax-d2 is worth
   what a router that only counts legal moves is worth. As a move prior for search, Jev's
   top 3 is no better than taking the first three moves in board order.

## Test C: full games, 20 openings × 2 colours (40 games per row)

Score: win 1, draw 0.5, loss 0. 95% bootstrap CI over openings.

| backend | prompt | vs heuristic | vs minimax-d2 | p50 ms |
|---|---|---|---|---|
| random | – | – | 0.000 | 0 |
| greedy | – | – | 0.037 | 0 |
| heuristic | – | (0.5) | 0.025 [0.00, 0.06] | 0 |
| **facts** (rule over v2 facts) | – | **0.700** [0.60, 0.80] | **0.200** [0.07, 0.33] | 0 |
| minimax-d1 | – | – | 0.125 | 0 |
| minimax-d4 | – | – | 0.738 | 0 |
| jev | v1 | 0.125 [0.03, 0.25] | 0.013 | 113–140 |
| jev | v2 | 0.575 [0.42, 0.75] | 0.050 | 112–130 |
| laya-framework | v1 | 0.212 [0.09, 0.35] | 0.000 | 38–40 |
| laya-framework | v2 | 0.425 [0.28, 0.59] | 0.000 | 49–50 |
| semif | v1 | 0.188 [0.09, 0.29] | 0.000 | 257–272 |
| semif | v2 | 0.325 [0.20, 0.45] | 0.050 | 342–424 |
| clef-flash | v1 | 0.163 [0.05, 0.31] | 0.000 | 577–620 |
| clef-flash | v2 | 0.163 [0.06, 0.26] | 0.000 | 674–855 |
| clef (27B) | v2 | 0.487 [0.36, 0.61] | 0.050 [0.00, 0.12] | 1751–2173 |

Runs: base-games-20261103-225250, m2-base-games-20261103-2303{31,33},
m2-v1-games-20261103-{225758,225838,230736,232426}, m2-v2-games-20261103-{225906,225943,234809},
m2-v2-games-20261104-001156; Clef 27B: m2-v2-games-20261104-{103537,111412}.

## Test B: move regret against the oracle (500 frozen positions)

Exact: the 200 positions with ≤ 20 empties, regret in final discs under perfect play.
Proxy: 300 earlier positions, scored by depth-10 search in eval points. Skill is
1 − regret / regret of a uniform random move.

| backend | prompt | exact best | exact regret (discs) | exact skill | proxy best | Δ regret vs heuristic, paired [95% CI] |
|---|---|---|---|---|---|---|
| random | – | 25.5% | 9.38 | 0.02 | 13.0% | +1.25 [−0.28, +2.86] |
| greedy | – | 28.0% | 11.36 | −0.19 | 12.0% | +3.22 [+1.54, +4.91] |
| heuristic | – | 34.5% | 8.14 | 0.15 | 23.0% | 0 |
| **facts** | – | **47.0%** | **4.96** | **0.48** | 27.7% | **−3.18** [−4.42, −2.04] |
| minimax-d2 | – | 72.5% | 2.10 | 0.78 | 46.7% | −6.04 [−7.36, −4.80] |
| minimax-d4 | – | 77.5% | 2.03 | 0.79 | 61.0% | −6.11 [−7.38, −4.89] |
| jev | v1 | 26.5% | 8.54 | 0.10 | 19.7% | +0.40 [−1.12, +1.90] |
| jev | v2 | 39.0% | 7.77 | 0.18 | 20.7% | −0.37 [−1.80, +1.13] |
| laya-framework | v1 | 25.0% | 10.51 | −0.10 | 14.3% | +2.37 [+0.86, +4.00] |
| laya-framework | v2 | 22.5% | 10.97 | −0.15 | 12.7% | +2.83 [+1.26, +4.38] |
| semif | v1 | 33.0% | 8.30 | 0.13 | 19.0% | +0.17 [−1.35, +1.68] |
| semif | v2 | 38.5% | 8.68 | 0.09 | 21.1% | +0.54 [−1.14, +2.33] |
| clef-flash | v1 | 28.0% | 8.88 | 0.07 | 23.3% | +0.74 [−0.77, +2.33] |
| clef-flash | v2 | 34.5% | 9.10 | 0.05 | 18.0% | +0.95 [−0.57, +2.54] |
| clef (27B) | v1 | 31.5% | 8.02 | 0.16 | 18.7% | −0.12 [−1.56, +1.34] |
| **clef (27B)** | v2 | **42.5%** | **6.70** | 0.30 | 22.3% | **−1.44** [−2.75, −0.01] |

Runs: m2-base-regret-20261103-234248, m2-v1-regret-20261103-{225941,230138},
m2-v2-regret-20261103-{230157,233617}; Clef 27B: m2-v{1,2}-regret-20261104-{100510,101704}.
Clef 27B v2 beats Clef-Flash v2 by 2.40 discs [1.14, 3.65], paired on the exact positions.

Minimax's exact rows include its own exact solve at ≤ 14 empties, which is why it is
perfect in the `final` stratum. SemIf's quality numbers exclude its 11 rejected positions
(fallbacks are never scored as model output); none of them are exact positions.

### Test D strata (best-move rate)

v2's gain is concentrated where the facts nearly answer the question. In the `final`
phase (≤ 14 empties) Jev goes from 38% to 54%, SemIf from 40% to 54%, Clef-Flash from 37%
to 52%. With `can_force_pass`, Jev goes from 38% to 69%, because v2 tells it when the
opponent must pass. On `greedy_trap` positions (the max-flips move costs ≥ 4 discs or
≥ 15 points) every model scores below the heuristic (24%), and v2 makes it worse: Jev
18% → 14%, Clef-Flash 21% → 11%. Clef 27B is the exception (20% → 20%), but it is still below the table. Given a `flips` count, the models lean towards flipping
more. The full table is in `runs/report.md`.

## §3: confidence and hybrids

`s1othello analyze` (output: `docs/analysis-m2.json`). AUC of max_prob for "picked an
optimal move", next to the trivial predictor 1/n_legal (fewer options means a higher
max_prob mechanically, and those positions are also easier):

| model | prompt | AUC(conf) | AUC(1/n_legal) | AUC(conf × n_legal) |
|---|---|---|---|---|
| jev | v1 | 0.706 | 0.707 | 0.417 |
| jev | v2 | 0.677 | 0.721 | 0.361 |
| laya-framework | v1 | 0.685 | 0.730 | 0.288 |
| laya-framework | v2 | 0.744 | 0.745 | 0.297 |
| semif | v1 | 0.635 | 0.659 | 0.360 |
| semif | v2 | 0.663 | 0.675 | 0.398 |
| clef-flash | v1 | 0.676 | 0.675 | 0.423 |
| clef-flash | v2 | 0.708 | 0.710 | 0.460 |
| clef (27B) | v1 | 0.684 | 0.680 | 0.514 |
| clef (27B) | v2 | 0.698 | 0.661 | 0.478 |

The simulated gate (route to minimax-d2 below a threshold) is within about ±3 points of
routing the same share at random, except SemIf v2 and Jev v2 at 25–50% share, where it is
+2 to +4 points. Clef 27B v2's gate, at 25/50/75% share: 36.2/44.0/50.4% best moves vs
37.0/43.7/50.4% routing at random. Its small AUC edge does not turn into a better gate.

**In play** (Jev v2, vs minimax-d2, 40 games each; the search share is endogenous and was
measured from the routes in calls.jsonl):

| router | share decided by search | score |
|---|---|---|
| jev alone | 0% | 0.050 |
| jev-coin40 (random 40%) | 38% | 0.037 [0.00, 0.10] |
| jev-count9 (≥ 9 legal moves) | 24% | 0.125 [0.03, 0.25] |
| **jev-gate** (max_prob < 0.5) | 40% | **0.175** [0.07, 0.30] |
| jev-count7 (≥ 7 legal moves) | 62% | 0.237 [0.11, 0.38] |

Interpolating the count router to a 40% share puts it at about 0.17, level with the gate.
The gate does beat blind routing, but by exactly what counting moves gives.

**Prune** (minimax-d2 searches only a prior's top 3): facts 0.350, heuristic 0.325,
first-three-in-board-order (`random-prune3`: random's uniform probabilities tie) 0.100,
**jev 0.062**. Jev's ranking gives search nothing to work with.

Runs: m3-games-20261103-{231448,231501,231637,231730,231825}.

## Caveats

- **Clef 27B needed a BIOS change.** On this Framework, ROCm allocates from the VRAM carve-out
  when there is one and from GTT (system RAM) otherwise. At a 64 GiB carve-out, allocations
  went to GTT, and the load hit the RAM limit twice: once while ComfyUI, LTX-2 and a
  transcriber shared the RAM, and again with every model server paused (a watchdog stopped
  it at 0.8 GB available). At a 96 GB carve-out (2026-11-04) it loaded in VRAM, using 68 GB
  with Laya and SemIf still up, and ran at 1.4–2.2 s per decision with no fallbacks. The v1
  games were not run.

- 40 games per Test C cell. CIs are wide (±0.1–0.15 on score), and the tables print them.
- Proxy regret (> 20 empties) is in eval points from my own depth-10 search, not an
  external engine. Edax was not used (auto mode blocked building third-party code), so
  read the proxy columns as a ranking signal only. The exact columns don't depend on it.
- One prompt wording per version. Board-representation ablations (PLAN.md §4) were not run.
- Laya does better in v2 games against the heuristic (0.43) while its regret gets worse.
  Playing a fixed weak opponent rewards exploiting that opponent, which a position oracle
  does not measure.
