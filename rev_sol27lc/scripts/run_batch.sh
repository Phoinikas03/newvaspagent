#!/bin/bash
# Run one arm over all systems, one GPU per system, at most one system per GPU.
#
# GPU ownership is tracked by driver PID, not by nvidia-smi memory: an agent run
# spends minutes preparing inputs before it launches any VASP, so a memory-based
# "is this GPU free" test hands the same GPU to several systems at once.
#
# Usage: run_batch.sh atomate2|agent [rep]
ARM="${1:?arm required}"; REP="${2:-rep1}"
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
mapfile -t UUIDS < <(nvidia-smi --query-gpu=uuid --format=csv,noheader)
mapfile -t SYSTEMS < <(ls "$EXP/data" | grep -v '\.json$' | sort)
NGPU=${#UUIDS[@]}
declare -A OWNER=()
echo "arm=$ARM rep=$REP systems=${#SYSTEMS[@]} gpus=$NGPU"

free_slot() {
  while true; do
    for ((g=0; g<NGPU; g++)); do
      pid="${OWNER[$g]:-}"
      if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then echo "$g"; return; fi
    done
    sleep 15
  done
}

for s in "${SYSTEMS[@]}"; do
  if [ "$ARM" = "atomate2" ]; then outdir="$EXP/runs_atomate2/$s"; else outdir="$EXP/runs_agent/$REP/$s"; fi
  if [ -f "$outdir/run_meta.json" ] && grep -q '"status": "completed"' "$outdir/run_meta.json" 2>/dev/null; then
    echo "skip $s (already completed)"; continue
  fi
  g=$(free_slot); gpu="${UUIDS[$g]}"
  if [ "$ARM" = "atomate2" ]; then
    nohup "$EXP/scripts/launch_atomate2.sh" --system "$s" --gpu-uuid "$gpu" > "$EXP/runs_atomate2/$s.log" 2>&1 &
  else
    mkdir -p "$EXP/runs_agent/$REP"
    nohup "$EXP/scripts/launch_agent.sh" --system "$s" --gpu-uuid "$gpu" --rep "$REP" > "$EXP/runs_agent/$REP/$s.log" 2>&1 &
  fi
  OWNER[$g]=$!
  echo "  launched $s -> gpu$g pid=${OWNER[$g]}"
done
wait
echo "batch done: $ARM $REP"
