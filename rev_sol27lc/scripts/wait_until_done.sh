#!/bin/bash
# Block until the agent rep finishes (or nothing is running any more), then
# print a summary. Also surfaces crashes and pending questions as they appear.
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc
REP="${1:-rep1}"; TARGET="${2:-27}"; MAXSEC="${3:-21600}"
t=0
while [ $t -lt $MAXSEC ]; do
  n=$(grep -l '"status": "completed"' "$EXP"/runs_agent/$REP/*/run_meta.json 2>/dev/null | wc -l)
  drivers=$(ps -eo cmd | grep -c "[r]un_agent_lc.py --system")
  crashed=$(grep -l "EXCEPTION" "$EXP"/runs_agent/$REP/*/driver.log 2>/dev/null | wc -l)
  pend=$(ls "$EXP"/runs_agent/$REP/*/PENDING_QUESTION.md 2>/dev/null | wc -l)
  if [ "$n" -ge "$TARGET" ]; then echo "ALL DONE: $n/$TARGET completed"; break; fi
  if [ "$drivers" -eq 0 ] && [ "$t" -gt 120 ]; then
    echo "NO DRIVERS LEFT but only $n/$TARGET completed (crashed_logs=$crashed)"; break
  fi
  if [ "$pend" -gt 0 ]; then echo "PENDING QUESTIONS: $pend (t=${t}s, completed=$n)"; break; fi
  sleep 60; t=$((t+60))
done
echo "--- final ---"
echo "completed=$(grep -l '"status": "completed"' "$EXP"/runs_agent/$REP/*/run_meta.json 2>/dev/null | wc -l)/$TARGET"
echo "crashed_logs=$(grep -l 'EXCEPTION' "$EXP"/runs_agent/$REP/*/driver.log 2>/dev/null | wc -l)"
grep -h '"status"' "$EXP"/runs_agent/$REP/*/run_meta.json 2>/dev/null | sort | uniq -c
