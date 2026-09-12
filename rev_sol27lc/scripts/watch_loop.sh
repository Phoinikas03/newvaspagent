#!/bin/bash
# Append a status line every 2 min so progress is auditable after the fact.
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc
while true; do
  ts=$(date '+%H:%M:%S')
  a2=$(grep -l '"status": "completed"' "$EXP"/runs_atomate2/*/run_meta.json 2>/dev/null | wc -l)
  ag=$(grep -l '"status": "completed"' "$EXP"/runs_agent/*/*/run_meta.json 2>/dev/null | wc -l)
  run=$(ps -eo cmd | grep -cE "run_atomate2\.py|run_agent_lc\.py" )
  gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader | tr '\n' ' ')
  cust=$(grep -hoE "ERROR:custodian\.custodian:\w+" "$EXP"/runs_atomate2/*.log 2>/dev/null | wc -l)
  echo "$ts atomate2=$a2/27 agent=$ag drivers=$run custodian_events=$cust gpu=[$gpu]"
  sleep 120
done
