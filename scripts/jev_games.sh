#!/usr/bin/env bash
# Test C for Jev from the Mac: both prompt versions x two opponents, 20 paired openings.
set -u
export TYPESAFE_API_KEY_FILE=${TYPESAFE_API_KEY_FILE:-./Jev.key}
for pv in v1 v2; do
  for opp in heuristic minimax-d2; do
    uv run s1othello eval --mode games --backends jev --opponent "$opp" --openings 20 \
      --prompt-version "$pv" --concurrency 4 --tag "m2-$pv"
  done
done
