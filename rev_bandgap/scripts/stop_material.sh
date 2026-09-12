#!/bin/bash
# Stop one material's agent driver and its VASP processes.
# Candidates are verified through /proc rather than matched with pkill -f,
# whose pattern also matches the shell running the script.
MAT="${1:?material required}"
SELF=$$; PARENT=$PPID
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap

for p in $(ls /proc | grep -E '^[0-9]+$'); do
  [ "$p" = "$SELF" ] || [ "$p" = "$PARENT" ] && continue
  cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
  case "$cmd" in
    *python*run_agent_bg.py*--system\ "$MAT"\ *) echo "driver $p"; kill -TERM "$p" ;;
  esac
done
sleep 5
for p in $(ls /proc | grep -E '^[0-9]+$'); do
  exe=$(readlink -f "/proc/$p/exe" 2>/dev/null) || continue
  case "$exe" in */vasp_std|*/vasp_gpu) ;; *) continue ;; esac
  cwd=$(readlink -f "/proc/$p/cwd" 2>/dev/null)
  case "$cwd" in "$EXP"/runs_agent/*/"$MAT"/*) echo "vasp $p ($cwd)"; kill -TERM "$p" ;; esac
done
sleep 6
echo "--- after ---"
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader | paste -sd' '
