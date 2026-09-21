#!/bin/bash
# Stop this experiment's agent drivers and their VASP processes.
#
# Deliberately not `pkill -f`: the pattern would match this script's own command
# line (and the shell that launched it), which is how earlier attempts killed
# themselves mid-cleanup. Every candidate is verified through /proc before it is
# signalled, and the script's own process tree is excluded.
SELF=$$; PARENT=$PPID
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

signal_matching() {
  local pattern="$1" sig="$2" label="$3" n=0
  for p in $(ls /proc | grep -E '^[0-9]+$'); do
    [ "$p" = "$SELF" ] && continue
    [ "$p" = "$PARENT" ] && continue
    cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
    case "$cmd" in
      $pattern) kill "-$sig" "$p" 2>/dev/null && { echo "  $label $p"; n=$((n+1)); } ;;
    esac
  done
  echo "$label: signalled $n"
}

echo "stopping batch drivers"
signal_matching '*run_batch.sh*agent*' TERM batch
sleep 2
echo "stopping agent drivers"
signal_matching '*python*run_agent_lc.py*' TERM driver
sleep 6

echo "stopping VASP owned by this experiment"
n=0
for p in $(ls /proc | grep -E '^[0-9]+$'); do
  exe=$(readlink -f "/proc/$p/exe" 2>/dev/null) || continue
  case "$exe" in */vasp_std|*/vasp_gpu) ;; *) continue ;; esac
  cwd=$(readlink -f "/proc/$p/cwd" 2>/dev/null)
  case "$cwd" in "$EXP"/runs_agent/*) kill -TERM "$p" 2>/dev/null && { echo "  vasp $p ($cwd)"; n=$((n+1)); } ;; esac
done
echo "vasp: signalled $n"
sleep 6

echo "--- remaining ---"
left=0
for p in $(ls /proc | grep -E '^[0-9]+$'); do
  [ "$p" = "$SELF" ] && continue
  [ "$p" = "$PARENT" ] && continue
  cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null) || continue
  case "$cmd" in *python*run_agent_lc.py*|*run_batch.sh*agent*) echo "  STILL: $p"; left=$((left+1)) ;; esac
done
echo "drivers left: $left"
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | paste -sd' '
