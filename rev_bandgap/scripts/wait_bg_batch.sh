#!/bin/bash
# Block until the band-gap batch finishes, a material needs an answer, or it stalls.
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap
SELF=$$; t=0; MAX=${1:-72000}
while [ $t -lt $MAX ]; do
  done_n=$(grep -l '"status": "completed"' "$EXP"/runs_agent/rep1/*/run_meta.json 2>/dev/null | wc -l)
  pend=$(ls "$EXP"/runs_agent/rep1/*/PENDING_QUESTION.md 2>/dev/null | wc -l)
  batch=0
  for p in $(ls /proc | grep -E '^[0-9]+$'); do
    [ "$p" = "$SELF" ] && continue
    c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
    case "$c" in *run_batch_bg.sh*) batch=1 ;; esac
  done
  if [ "$pend" -gt 0 ]; then echo "$(date +%H:%M:%S) PENDING QUESTION (completed=$done_n/5)"; break; fi
  if [ "$batch" -eq 0 ]; then echo "$(date +%H:%M:%S) batch finished (completed=$done_n/5)"; break; fi
  if [ "$done_n" -ge 5 ]; then echo "$(date +%H:%M:%S) all five done"; break; fi
  sleep 300; t=$((t+300))
done
echo "--- state ---"
for d in "$EXP"/runs_agent/rep1/*/; do
  m=$(basename "$d"); case "$m" in .*) continue;; esac
  st=$(python3 -c "
import json,sys
try: print(json.load(open('$d/run_meta.json')).get('status'))
except Exception: print('running')" 2>/dev/null)
  echo "  $m: $st"
done
