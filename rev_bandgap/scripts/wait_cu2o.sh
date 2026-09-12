#!/bin/bash
# Report when the Cu2O hybrid SCF converges, its VASP exits, or 2 h pass.
D=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap/runs_agent/rep1/Cu2O
t=0; MAX=7200
while [ $t -lt $MAX ]; do
  running=0
  for p in $(ls /proc | grep -E '^[0-9]+$'); do
    exe=$(readlink -f "/proc/$p/exe" 2>/dev/null) || continue
    case "$exe" in */vasp_gpu|*/vasp_std) ;; *) continue ;; esac
    cwd=$(readlink -f "/proc/$p/cwd" 2>/dev/null)
    case "$cwd" in "$D"/*) running=1 ;; esac
  done
  steps=$(grep -cE "^DMP:" "$D/hse_scf/vasp_hse.log" 2>/dev/null || echo 0)
  last=$(grep -E "^DMP:" "$D/hse_scf/vasp_hse.log" 2>/dev/null | tail -1 | awk '{print $4}')
  if [ "$running" -eq 0 ]; then
    echo "$(date +%H:%M:%S) VASP exited after $steps SCF steps (last dE=$last)"; break
  fi
  if grep -q "reached required accuracy\|aborting loop because EDIFF" "$D/hse_scf/vasp_hse.log" 2>/dev/null; then
    echo "$(date +%H:%M:%S) SCF converged after $steps steps (last dE=$last)"; break
  fi
  sleep 120; t=$((t+120))
done
echo "--- state ---"
echo "steps=$(grep -cE '^DMP:' "$D/hse_scf/vasp_hse.log" 2>/dev/null)"
grep -E "^DMP:" "$D/hse_scf/vasp_hse.log" 2>/dev/null | tail -3
ls "$D"/hse_scf/vasprun.xml 2>/dev/null && echo "vasprun.xml present"
python3 -c "
import json,os
p='$D/run_meta.json'
print('driver status:', json.load(open(p)).get('status') if os.path.exists(p) else 'still running')"
