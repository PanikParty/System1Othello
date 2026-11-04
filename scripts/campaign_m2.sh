#!/usr/bin/env bash
# M2 campaign on the Framework: Test C + Test B/D for the locally served models.
# Run from ~/System1Othello:  nohup scripts/campaign_m2.sh > runs/logs/m2.log 2>&1 &
# Models run one after another so they don't contend for the GPU (latency is a metric).
set -u
. scripts/framework_env.sh
S=~/.local/bin/uv
MODELS="laya-framework semif clef-flash"

# Test B/D baselines (they ignore the prompt; one run is enough)
$S run s1othello eval --mode regret --backends random,greedy,heuristic,minimax-d1,minimax-d2,minimax-d4 \
  --positions positions/v1.jsonl --tag m2-base

for pv in v1 v2; do
  $S run s1othello eval --mode regret --backends ${MODELS// /,} --positions positions/v1.jsonl \
    --prompt-version "$pv" --tag "m2-$pv"
  for opp in heuristic minimax-d2; do
    $S run s1othello eval --mode games --backends ${MODELS// /,} --opponent "$opp" --openings 20 \
      --prompt-version "$pv" --tag "m2-$pv"
  done
done
