#!/bin/bash
# Wait for the in-flight batch (which still has the old ORDER in memory) to exit,
# then run GaP from its own script. Editing the running script is not an option:
# bash reads a script incrementally by byte offset, so changing it underneath a
# running shell can corrupt the next command it reads.
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap
SELF=$$
while true; do
  alive=0
  for p in $(ls /proc | grep -E '^[0-9]+$'); do
    [ "$p" = "$SELF" ] && continue
    c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
    case "$c" in *run_batch_bg.sh*agent*) alive=1 ;; esac
  done
  [ "$alive" -eq 0 ] && break
  sleep 60
done
echo "$(date '+%H:%M:%S') previous batch exited; starting GaP"
exec "$EXP/scripts/run_batch_bg_gap.sh" agent rep1 86400
