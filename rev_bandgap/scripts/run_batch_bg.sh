#!/bin/bash
# Band-gap pilot: one material at a time, each owning every usable GPU.
#
# Order is by expected cost, cheapest first, rather than alphabetical: an
# expensive material running first delays every cheap result behind it, and the
# cost multiplier this pilot exists to measure is better estimated from several
# cheap points than from one expensive one. GPU 2 is excluded; it throttles to
# roughly 400 MHz under load and would drag down any job spanning it.
ARM="${1:-agent}"; REP="${2:-rep1}"; BUDGET="${3:-86400}"
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap
EXCLUDE_GPU_INDEX=2
ORDER=(GaAs ZnO Cu2O Ga2O3 Si)

mapfile -t UUIDS < <(nvidia-smi --query-gpu=index,uuid --format=csv,noheader \
  | awk -F', ' -v skip="$EXCLUDE_GPU_INDEX" '$1 != skip {print $2}')
ALLOC=$(IFS=,; echo "${UUIDS[*]}")
echo "arm=$ARM rep=$REP order=${ORDER[*]} gpus=${#UUIDS[@]} (GPU $EXCLUDE_GPU_INDEX excluded) budget=${BUDGET}s"

for m in "${ORDER[@]}"; do
  [ -d "$EXP/data/$m" ] || { echo "skip $m (no input)"; continue; }
  outdir="$EXP/runs_agent/$REP/$m"
  if [ -f "$outdir/run_meta.json" ] && grep -q '"status": "completed"' "$outdir/run_meta.json" 2>/dev/null; then
    echo "skip $m (already completed)"; continue
  fi
  mkdir -p "$EXP/runs_agent/$REP"
  echo "=== $(date '+%H:%M:%S') starting $m on ${#UUIDS[@]} GPUs"
  "$EXP/scripts/launch_agent_bg.sh" --system "$m" --gpu-uuid "$ALLOC" --rep "$REP" \
    --budget-sec "$BUDGET" > "$EXP/runs_agent/$REP/$m.log" 2>&1
  echo "=== $(date '+%H:%M:%S') finished $m status=$(python3 -c "
import json,sys
try: print(json.load(open('$outdir/run_meta.json')).get('status'))
except Exception: print('unknown')" 2>/dev/null)"
done
echo "batch done: $ARM $REP"
