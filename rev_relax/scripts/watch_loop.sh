#!/bin/bash
# Append a status line every 2 min so progress is auditable after the fact.
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
while true; do
  ts=$(date '+%F %T')
  line=""
  for r in "$EXP"/runs_agent/*/; do
    [ -d "$r" ] || continue
    rn=$(basename "$r")
    c=$(grep -l '"status": "completed"' "$r"*/run_meta.json 2>/dev/null | wc -l)
    e=$(ls "$r"*/run_meta.json 2>/dev/null | wc -l)
    line="$line $rn=$c/$e"
  done
  run=$(ps -eo cmd | grep -c "[r]un_agent_relax\.py")
  gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | tr '\n' ' ')
  echo "$ts completed/ended:$line drivers=$run gpu=[$gpu]"
  sleep 120
done
