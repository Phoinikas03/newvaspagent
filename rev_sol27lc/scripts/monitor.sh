#!/bin/bash
# At-a-glance status of both arms.
EXP=/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc
echo "=== atomate2 arm ==="
printf "%-10s %-14s %-6s %s\n" SYSTEM STATUS JOBS LAST
for d in "$EXP"/runs_atomate2/*/; do
  s=$(basename "$d"); [ -d "$d" ] || continue
  st=$(python3 -c "import json;print(json.load(open('$d/run_meta.json')).get('status','running'))" 2>/dev/null || echo "-")
  n=$(ls -d "$d"/job_* 2>/dev/null | wc -l)
  last=$(grep -E "Starting job|Finished job" "$EXP/runs_atomate2/$s".*.log 2>/dev/null | tail -1 | sed 's/.*INFO //' | cut -c1-46)
  printf "%-10s %-14s %-6s %s\n" "$s" "$st" "$n" "$last"
done
echo
echo "=== agent arm ==="
printf "%-10s %-6s %-16s %-7s %-6s %s\n" SYSTEM REP STATUS ROUNDS QA LASTQ
for d in "$EXP"/runs_agent/*/*/; do
  [ -d "$d" ] || continue
  rep=$(basename "$(dirname "$d")"); s=$(basename "$d")
  python3 - "$d" "$rep" "$s" <<'PY' 2>/dev/null || printf "%-10s %-6s %-16s\n" "$s" "$rep" "starting"
import json,sys,os
d,rep,s=sys.argv[1:4]
p=os.path.join(d,"run_meta.json")
if not os.path.exists(p):
    print(f"{s:<10} {rep:<6} {'running':<16}"); raise SystemExit
m=json.load(open(p)); qa=m.get("qa",[])
lastq=qa[-1]["category"] if qa else "-"
print(f"{s:<10} {rep:<6} {m.get('status','?'):<16} {m.get('rounds',0):<7} {len(qa):<6} {lastq}")
PY
done
echo
echo "=== GPUs ==="
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
