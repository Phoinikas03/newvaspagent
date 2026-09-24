#!/bin/bash
# Queue every system of every listed rep, one GPU per system, at most one
# system per GPU. Reps are queued rep-major (all of rep1, then rep2, ...), so a
# rep's systems run side by side as in Sol27LC; the next rep starts filling GPUs
# as the previous one's tail frees them instead of leaving 6 cards idle.
# Within a rep, systems start longest-first (data/launch_order.tsv).
#
# GPU ownership is tracked by driver PID, not by nvidia-smi memory: an agent run
# spends minutes preparing inputs before it launches any VASP.
#
# EXCLUDE_GPU_INDEX: comma-separated nvidia-smi indices not to use (d03: 5).
#
# Usage: EXCLUDE_GPU_INDEX=5 run_batch.sh rep1 [rep2 rep3 ...]
[ $# -ge 1 ] || { echo "usage: run_batch.sh rep1 [rep2 ...]"; exit 2; }
REPS=("$@")
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
mapfile -t UUIDS < <(nvidia-smi --query-gpu=index,uuid --format=csv,noheader \
  | awk -F', ' -v skip="${EXCLUDE_GPU_INDEX:-}" '
      BEGIN { n = split(skip, a, ","); for (i = 1; i <= n; i++) drop[a[i] + 0] = 1 }
      !($1 + 0 in drop) { print $2 }')
mapfile -t SYSTEMS < <(grep -v '^#' "$EXP/data/launch_order.tsv" | cut -f1)
NGPU=${#UUIDS[@]}
declare -A OWNER=()
echo "$(date '+%F %T') reps=${REPS[*]} systems=${#SYSTEMS[@]} gpus=$NGPU exclude=${EXCLUDE_GPU_INDEX:-none}"

free_slot() {
  while true; do
    for ((g=0; g<NGPU; g++)); do
      pid="${OWNER[$g]:-}"
      if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then echo "$g"; return; fi
    done
    sleep 15
  done
}

for rep in "${REPS[@]}"; do
  mkdir -p "$EXP/runs_agent/$rep"
  for s in "${SYSTEMS[@]}"; do
    outdir="$EXP/runs_agent/$rep/$s"
    if [ -f "$outdir/run_meta.json" ]; then
      echo "skip $rep/$s (run_meta.json exists: $(grep -o '"status": "[^"]*"' "$outdir/run_meta.json"))"; continue
    fi
    g=$(free_slot); gpu="${UUIDS[$g]}"
    nohup "$EXP/scripts/launch_agent.sh" --system "$s" --gpu-uuid "$gpu" --rep "$rep" \
      > "$EXP/runs_agent/$rep/$s.log" 2>&1 &
    OWNER[$g]=$!
    echo "$(date '+%F %T')  launched $rep/$s -> slot$g $gpu pid=${OWNER[$g]}"
    sleep 5
  done
done
wait
echo "$(date '+%F %T') batch done: ${REPS[*]}"
