#!/bin/bash
# Block until every listed rep has a run_meta.json for all 40 systems (or no
# driver is left), returning early when a question is pending.
# Usage: wait_until_done.sh "rep1 rep2 rep3" [maxsec]
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
REPS="${1:-rep1}"; MAXSEC="${2:-86400}"
NSYS=$(grep -vc '^#' "$EXP/data/launch_order.tsv")
TARGET=$(( NSYS * $(echo $REPS | wc -w) ))
t=0
while [ $t -lt $MAXSEC ]; do
  ended=0; for r in $REPS; do ended=$((ended + $(ls "$EXP"/runs_agent/$r/*/run_meta.json 2>/dev/null | wc -l))); done
  drivers=$(ps -eo cmd | grep -c "[r]un_agent_relax.py --system")
  pend=$(ls "$EXP"/runs_agent/*/*/PENDING_QUESTION.md 2>/dev/null | wc -l)
  if [ "$ended" -ge "$TARGET" ]; then echo "ALL ENDED: $ended/$TARGET"; break; fi
  if [ "$drivers" -eq 0 ] && [ "$t" -gt 120 ]; then echo "NO DRIVERS LEFT, $ended/$TARGET ended"; break; fi
  if [ "$pend" -gt 0 ]; then echo "PENDING QUESTIONS: $pend (t=${t}s, ended=$ended/$TARGET)"; break; fi
  sleep 60; t=$((t+60))
done
echo "--- status counts ---"
for r in $REPS; do echo "[$r]"; grep -h '"status"' "$EXP"/runs_agent/$r/*/run_meta.json 2>/dev/null | sort | uniq -c; done
