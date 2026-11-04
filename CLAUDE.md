# s1othello: conventions for Claude Code

System One models (TypeSafe Jev, Clef, Laya, SemIf) play Othello. Companion to System1Doom.
The design is in PLAN.md; status and results are in README.md and docs/.

## Rules
- Python 3.11+ managed with `uv`, type hints, pydantic for answers. `pytest` unit tests never touch the network.
- **Code computes the geometry, the model only judges.** The model is only ever offered the legal moves.
- **Build the heuristic first, the model second.** Every harness feature must work with the baselines
  (`random`, `greedy`, `heuristic`, `minimax-d*`) before a model backend is wired to it.
- Never hardcode or print API keys. `TYPESAFE_API_KEY` (or `./Jev.key`, overridable with
  `TYPESAFE_API_KEY_FILE`), `CLEF_API_KEY`, `LAYA_API_KEY` come from env or gitignored files.
- Tests that call a real model server are marked `@pytest.mark.live` and skipped by default (`-m live`).
- Every decision is logged to `runs/<id>/calls/<backend>.jsonl` with `prompt_version`. Fallbacks are
  labelled `fallback` and never counted as model output; single-legal-move positions are `forced`
  (no call, excluded from stats).
- Prompt text lives in `prompts/<version>/questions.yaml`, never inlined in Python.
- `runs/` is gitignored; results go into docs/ with the run ids they came from. Frozen position
  sets in `positions/` ARE committed and never regenerated in place (new set = new file name).
- Commit once per milestone, with a short result note derived from `runs/` in the commit body.

## Engine facts (checked 2026-11-03; don't re-derive)
- Square index `sq = row*8 + col`, A1 = bit 0 = `board[0][0]` (top-left), H8 = bit 63.
- `native/ob.c` is compiled on first use into `~/.cache/s1othello/` (keyed by source hash). On macOS
  the Bash tool's shell runs under Rosetta, so the build passes `-arch <python's arch>`; never `-march=native` there.
- Native movegen matches engine.py on 18k positions; exact solves match brute force.
- Exact scores = final disc differential, empties uncounted (matches `engine.disc_counts`).
- Exact all-moves solve, M-series Mac: 14 empties ~40 ms, 16 ~0.5 s, 18 ~3 s, 20 ~24 s (single thread).
  Midgame search depth 8 ~0.13 s, depth 10 ~2 s.
- Every non-model backend is deterministic, so Test C needs `openings.make_openings` (paired, colour-swapped).

## Framework host
- `ssh framework`; models: laya-serve :8000, semif-serve :8010, clef-flash-serve :8100, clef-serve :8101
  (stopped by default). Clef key: `set -a; . ~/clef/clef-serve.env; set +a`.
- `~/System1Othello` there is a plain uv project (no torch), so `uv sync` is safe in it
  (unlike ~/System1Doom). Sync code with a git bundle.

## Common commands
```bash
uv run pytest -q
uv run s1othello play --black heuristic --white minimax-d2 --opening-seed 1
uv run s1othello eval --mode games --backends heuristic,jev --opponent minimax-d2 --openings 20 --tag m2
uv run s1othello eval --mode regret --backends heuristic,jev --positions positions/v1.jsonl --tag m2
uv run s1othello build-positions --out positions/v1.jsonl --per-phase 100 --workers 30
uv run s1othello report
```
