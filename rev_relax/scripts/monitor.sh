#!/bin/bash
# At-a-glance status of every agent run.
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
printf "%-14s %-6s %-16s %-7s %-4s %-7s %s\n" SYSTEM REP STATUS ROUNDS QA HOURS LASTQ
for d in "$EXP"/runs_agent/*/*/; do
  [ -d "$d" ] || continue
  rep=$(basename "$(dirname "$d")"); s=$(basename "$d")
  python3 - "$d" "$rep" "$s" <<'PY' 2>/dev/null || printf "%-14s %-6s %-16s\n" "$s" "$rep" "starting"
import json,sys,os,time
d,rep,s=sys.argv[1:4]
p=os.path.join(d,"run_meta.json")
if not os.path.exists(p):
    t=os.path.getmtime(os.path.join(d,"POSCAR")) if os.path.exists(os.path.join(d,"POSCAR")) else time.time()
    print(f"{s:<14} {rep:<6} {'running':<16} {'':<7} {'':<4} {(time.time()-t)/3600:<7.1f}"); raise SystemExit
m=json.load(open(p)); qa=m.get("qa",[])
lastq=qa[-1]["category"] if qa else "-"
print(f"{s:<14} {rep:<6} {m.get('status','?')[:16]:<16} {m.get('rounds',0):<7} {len(qa):<4} {m.get('wall_seconds',0)/3600:<7.1f} {lastq}")
PY
done
echo
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
