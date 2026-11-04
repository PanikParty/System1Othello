#!/usr/bin/env bash
# Clef 27B lane on the Framework. 27B needs ~57 GB VRAM, so Clef-Flash is stopped first
# and always restarted at the end (also on failure).
# 2026-11-04: did not fit (OOM on load) while ComfyUI x2, LTX-2 and a transcriber shared
# the 62 GB of GTT memory; check `cat /sys/class/drm/card*/device/mem_info_gtt_used` first.
#   nohup scripts/campaign_clef27.sh > runs/logs/clef27.log 2>&1 &
set -u
. scripts/framework_env.sh
S=~/.local/bin/uv
restore() { systemctl --user stop clef-serve; systemctl --user start clef-flash-serve; echo "restored clef-flash-serve"; }
trap restore EXIT
systemctl --user stop clef-flash-serve
systemctl --user start clef-serve
for i in $(seq 1 120); do  # wait up to 20 min for the weights to load
  curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $CLEF_API_KEY" -H 'Content-Type: application/json' \
    -d '{"state":{},"questions":{"q":{"type":"noul","instructions":"ok?"}}}' http://127.0.0.1:8101/v1/systemone | grep -q 200 && break
  sleep 10
done
echo "clef-serve up after ~$((i * 10)) s"
for pv in v1 v2; do
  $S run s1othello eval --mode regret --backends clef --positions positions/v1.jsonl --prompt-version "$pv" --tag "m2-$pv"
done
for opp in heuristic minimax-d2; do
  $S run s1othello eval --mode games --backends clef --opponent "$opp" --openings 20 --prompt-version v2 --tag m2-v2
done
