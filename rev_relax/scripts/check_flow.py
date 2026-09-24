#!/usr/bin/env python3
"""Completion and flow check for one agent SR (structure relaxation) run.

Decided from files on disk, never from what the agent says. A *relaxation run*
is any directory in the workspace holding an OUTCAR whose INCAR asks for ionic
steps (NSW > 0, IBRION in 1/2/3); static single points (the convergence sweep,
if one was run) are counted separately.

The run is finished when at least one relaxation run
  * reached ionic convergence ("reached required accuracy"),
  * terminated normally (OUTCAR carries VASP's final timing block),
  * left a non-empty CONTCAR,
and no VASP process is still running inside the workspace; the most recently
written such run is the result. A second pass the agent has already launched
therefore holds completion back until it ends. A later relaxation that ended
without converging does not (an agent that copies a crashed OUTCAR into a
backup folder refreshes its mtime); it is listed in the notes instead.

verdict: conformant           -- finished, full relaxation (ISIF = 3)
         done_with_deviation  -- finished, but the final run did not relax the
                                 cell (ISIF != 3), which the task asked for
         in_progress          -- anything else
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

GENERAL_TIMING = "General timing and accounting"
REACHED = "reached required accuracy"


def read_incar(path: Path) -> dict:
    out = {}
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.split("#")[0].split("!")[0]
        for part in line.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k.strip().upper()] = v.strip()
    return out


def _int(value, default=None):
    try:
        return int(float(str(value).split()[0]))
    except (TypeError, ValueError, IndexError):
        return default


def vasp_running_in(workspace: Path) -> list[int]:
    """PIDs of VASP processes whose cwd lies inside this workspace."""
    root = str(workspace.resolve())
    pids = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            exe = os.readlink(f"/proc/{p}/exe")
            if not re.search(r"vasp_(std|gam|ncl|gpu)", os.path.basename(exe)):
                continue
            cwd = os.readlink(f"/proc/{p}/cwd")
        except OSError:
            continue
        if cwd == root or cwd.startswith(root + "/"):
            pids.append(int(p))
    return pids


def scan_runs(workspace: Path) -> tuple[list[dict], list[dict]]:
    relax, static = [], []
    for outcar in workspace.rglob("OUTCAR"):
        d = outcar.parent
        incar = read_incar(d / "INCAR")
        nsw = _int(incar.get("NSW"), 0)
        ibrion = _int(incar.get("IBRION"), -1 if nsw == 0 else 0)
        try:
            text = outcar.read_text(errors="replace")
            mtime = outcar.stat().st_mtime
        except OSError:
            continue
        contcar = d / "CONTCAR"
        row = {
            "dir": str(d.relative_to(workspace)) or ".",
            "mtime": mtime,
            "isif": _int(incar.get("ISIF"), 2),
            "nsw": nsw,
            "ibrion": ibrion,
            "ionic_converged": REACHED in text,
            "finished": GENERAL_TIMING in text,
            "ionic_steps": len(re.findall(r"^\s*\d+\s+F=", (d / "OSZICAR").read_text(errors="replace"), re.M))
            if (d / "OSZICAR").exists() else 0,
            "contcar": contcar.exists() and contcar.stat().st_size > 0,
        }
        (relax if nsw > 0 and ibrion in (1, 2, 3) else static).append(row)
    relax.sort(key=lambda r: r["mtime"])
    static.sort(key=lambda r: r["mtime"])
    return relax, static


def check(root: str) -> dict:
    ws = Path(root)
    relax, static = scan_runs(ws)
    running = vasp_running_in(ws)
    res = {
        "run": ws.name,
        "n_relax_runs": len(relax),
        "n_static_runs": len(static),
        "convergence_report": bool(list(ws.rglob("Convergence_Report.md"))),
        "vasp_running": running,
        "final": None,
        "notes": [],
    }
    good = [r for r in relax if r["ionic_converged"] and r["finished"] and r["contcar"]]
    final = res["final"] = good[-1] if good else None
    for r in relax:
        if final and r["mtime"] > final["mtime"] and not r["ionic_converged"]:
            res["notes"].append(f"later relaxation {r['dir']} did not converge (result taken from {final['dir']})")
    if relax and not good and not running:
        res["notes"].append("no relaxation has converged yet")
    done = bool(final and not running)
    if done and final["isif"] != 3:
        res["notes"].append(f"DEVIATION: final relaxation used ISIF={final['isif']} (cell not relaxed)")
    res["verdict"] = ("conformant" if final["isif"] == 3 else "done_with_deviation") if done else "in_progress"
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = [check(r) for r in args.roots if os.path.isdir(r)]
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    hdr = f"{'run':<14} {'relax':>5} {'static':>6} {'conv':>4} {'isif':>4} {'steps':>5} {'ionic':>5}  verdict"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        f = r["final"] or {}
        print(f"{r['run']:<14} {r['n_relax_runs']:>5} {r['n_static_runs']:>6} "
              f"{int(r['convergence_report']):>4} {f.get('isif', '-'):>4} {f.get('ionic_steps', '-'):>5} "
              f"{str(f.get('ionic_converged', '-')):>5}  {r['verdict']}"
              + ("  (vasp running)" if r["vasp_running"] else ""))
        for n in r["notes"]:
            print(f"    ! {n}")


if __name__ == "__main__":
    main()
