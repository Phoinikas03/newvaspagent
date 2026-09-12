#!/bin/bash
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap
while true; do
  done_n=$(grep -l '"status": "completed"' "$EXP"/runs_agent/rep1/*/run_meta.json 2>/dev/null | wc -l)
  act=$(ls -d "$EXP"/runs_agent/rep1/*/ 2>/dev/null | wc -l)
  gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader | tr '\n' ' ')
  echo "$(date '+%H:%M:%S') completed=$done_n/5 started=$act gpu=[$gpu]"
  sleep 300
done
