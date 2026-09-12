#!/bin/bash
# atomate2 band-gap arm: one GPU per material, all materials in parallel.
#
# One GPU each matches what the agent arm actually consumed -- it held a
# seven-GPU allocation but chose KPAR=1 for every material -- so GPU-hours are
# comparable between the arms even though the agent ran serially.
#
# GPUs are claimed by PID, not by nvidia-smi memory: a job spends minutes writing
# inputs before any VASP starts, and a memory-based check would hand the same
# card to several materials at once. GPU 2 is excluded (throttles to ~400 MHz),
# as is any card already busy with someone else's work.
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap
EXCLUDE_GPU_INDEX=2
MATERIALS=(GaAs GaP Si ZnO Cu2O)

busy_uuids=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | sort -u)
mapfile -t UUIDS < <(nvidia-smi --query-gpu=index,uuid --format=csv,noheader \
  | awk -F', ' -v skip="$EXCLUDE_GPU_INDEX" '$1 != skip {print $2}' \
  | grep -v -F -f <(echo "$busy_uuids"; echo "__none__"))
echo "usable GPUs: ${#UUIDS[@]} (GPU $EXCLUDE_GPU_INDEX excluded, busy cards skipped)"
if [ "${#UUIDS[@]}" -lt 1 ]; then echo "no free GPU"; exit 1; fi

declare -A OWNER=()
free_slot() {
  while true; do
    for ((g=0; g<${#UUIDS[@]}; g++)); do
      pid="${OWNER[$g]:-}"
      if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then echo "$g"; return; fi
    done
    sleep 20
  done
}

for m in "${MATERIALS[@]}"; do
  [ -d "$EXP/data/$m" ] || { echo "skip $m (no input)"; continue; }
  out="$EXP/runs_atomate2/$m"
  if [ -f "$out/run_meta.json" ] && grep -q '"status": "completed"' "$out/run_meta.json" 2>/dev/null; then
    echo "skip $m (already completed)"; continue
  fi
  g=$(free_slot); gpu="${UUIDS[$g]}"
  mkdir -p "$EXP/runs_atomate2"
  nohup "$EXP/scripts/launch_atomate2_bg.sh" --material "$m" --gpu-uuid "$gpu" \
    > "$EXP/runs_atomate2/$m.log" 2>&1 &
  OWNER[$g]=$!
  echo "$(date '+%H:%M:%S') launched $m -> slot$g pid=${OWNER[$g]}"
  sleep 5
done
wait
echo "batch done: atomate2 band-gap"
