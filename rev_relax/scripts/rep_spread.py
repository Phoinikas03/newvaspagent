#!/usr/bin/env python3
"""Run-to-run spread of the SR agent arm across reps.

Reads audit/results.json (collect_results.py) and reports
  * per rep: ended / completed counts, matched-to-expert count, median and
    mean RMSD vs expert, median |dV| -- the rep-level numbers to compare;
  * per system: RMSD vs expert in each rep, and the agent-vs-agent RMSD
    between the final structures of every pair of reps (StructureMatcher,
    angle_tol=30, as for the expert comparison), plus the volume spread.

Only systems whose run_meta.json says "completed" in *every* rep compared are
admitted to the per-system spread. A run still in progress has a real-looking
CONTCAR mid-relaxation; comparing it manufactures spread (the Sol27LC rep3
analysis hit exactly this). Rep-level counts use all ended runs.

Usage: rep_spread.py [--reps rep1,rep2,rep3] [--json]
"""
from __future__ import annotations

import itertools
import json
import statistics
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
from pymatgen.analysis.structure_matcher import StructureMatcher  # noqa: E402
from pymatgen.core import Structure  # noqa: E402

EXP = Path(__file__).resolve().parents[1]


def main() -> None:
    rows = json.loads((EXP / "audit" / "results.json").read_text())
    reps = sorted({r["rep"] for r in rows if r["rep"].startswith("rep")})
    if "--reps" in sys.argv:
        reps = sys.argv[sys.argv.index("--reps") + 1].split(",")
    by = {(r["rep"], r["system"]): r for r in rows if r["rep"] in reps}
    systems = sorted({s for _, s in by})

    per_rep = {}
    for rep in reps:
        rr = [r for (p, _), r in by.items() if p == rep]
        done = [r for r in rr if r["status"] == "completed"]
        rms = [r["rmsd_vs_expert"] for r in done if r.get("rmsd_vs_expert") is not None]
        dv = [abs(r["dV_pct"]) for r in done if r.get("dV_pct") is not None]
        per_rep[rep] = {
            "ended": sum(r["status"] != "running" for r in rr),
            "completed": len(done),
            "status_counts": {s: sum(r["status"] == s for r in rr) for s in sorted({r["status"] for r in rr})},
            "matched": len(rms),
            "rmsd_median": statistics.median(rms) if rms else None,
            "rmsd_mean": statistics.mean(rms) if rms else None,
            "abs_dV_pct_median": statistics.median(dv) if dv else None,
            "wall_h_total": round(sum(r["wall_h"] or 0 for r in rr), 2),
        }

    matcher = StructureMatcher(angle_tol=30)
    per_sys, excluded = {}, []
    for s in systems:
        rs = [by.get((rep, s)) for rep in reps]
        if not all(r and r["status"] == "completed" and r.get("final_dir") for r in rs):
            excluded.append(s)
            continue
        structs = {r["rep"]: Structure.from_file(EXP / "runs_agent" / r["rep"] / s / r["final_dir"] / "CONTCAR")
                   for r in rs}
        pair = {}
        for a, b in itertools.combinations(reps, 2):
            d = matcher.get_rms_dist(structs[a], structs[b])
            pair[f"{a}~{b}"] = round(d[0], 6) if d else None
        vols = [r["volume_A3"] for r in rs]
        per_sys[s] = {
            "rmsd_vs_expert": {r["rep"]: r.get("rmsd_vs_expert") for r in rs},
            "rmsd_between_reps": pair,
            "max_rmsd_between_reps": max((v for v in pair.values() if v is not None), default=None),
            "unmatched_pairs": sum(v is None for v in pair.values()),
            "volume_spread_pct": round(100 * (max(vols) - min(vols)) / statistics.mean(vols), 4),
            "dE_meV_atom": {r["rep"]: r.get("dE_meV_atom") for r in rs},
            "potcar_same": len({r.get("potcar") for r in rs}) == 1,
            "ldau": {r["rep"]: r.get("incar_LDAU") for r in rs},
        }

    out = {"reps": reps, "per_rep": per_rep, "per_system": per_sys,
           "excluded_not_completed_in_all": excluded}
    if "--json" in sys.argv:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    print(f"{'rep':<6} {'ended':>5} {'done':>5} {'match':>5} {'RMSD med':>9} {'RMSD mean':>9} {'|dV|% med':>9} {'GPU h':>7}")
    for rep, v in per_rep.items():
        f = lambda x, n=4: f"{x:.{n}f}" if isinstance(x, float) else "-"  # noqa: E731
        print(f"{rep:<6} {v['ended']:>5} {v['completed']:>5} {v['matched']:>5} {f(v['rmsd_median']):>9} "
              f"{f(v['rmsd_mean']):>9} {f(v['abs_dV_pct_median'], 2):>9} {v['wall_h_total']:>7}")
    print()
    print(f"{'system':<14} " + " ".join(f"{r:>8}" for r in reps) + f" {'maxRMSDrr':>9} {'dV%spread':>9}")
    for s, v in per_sys.items():
        cells = " ".join(f"{v['rmsd_vs_expert'][r]:>8.4f}" if v['rmsd_vs_expert'][r] is not None else f"{'nomatch':>8}"
                         for r in reps)
        m = v["max_rmsd_between_reps"]
        print(f"{s:<14} {cells} {m if m is None else round(m, 4):>9} {v['volume_spread_pct']:>9}")
    if excluded:
        print(f"\n# not completed in every rep (left out above): {' '.join(excluded)}")


if __name__ == "__main__":
    main()
