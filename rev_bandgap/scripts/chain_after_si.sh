#!/bin/bash
# Wait for the Si smoke test to end, then run the remaining materials serially.
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap
SELF=$$
while true; do
  n=0
  for p in $(ls /proc | grep -E '^[0-9]+$'); do
    [ "$p" = "$SELF" ] && continue
    cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
    case "$cmd" in *python*run_agent_bg.py*) n=$((n+1)) ;; esac
  done
  [ "$n" -eq 0 ] && break
  sleep 60
done
echo "$(date '+%H:%M:%S') Si finished; starting the remaining materials"
exec "$EXP/scripts/run_batch_bg.sh" agent rep1 86400
