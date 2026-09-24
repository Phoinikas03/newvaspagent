#!/usr/bin/env python3
"""Collect every agent SR run into one table (JSON + CSV).

Per <rep>/<system>: driver status and cost, the result relaxation chosen by
check_flow.py, the parameters the agent chose for it, and the comparison with
the expert reference in reference/<system>/:

  rmsd_vs_expert   pymatgen StructureMatcher(angle_tol=30).get_rms_dist(...)[0],
                   the normalised RMS used for relax_new.xlsx (RMSD_vs_expert),
                   so the numbers sit on the manuscript's scale; None = no match
  dV_pct           final volume vs the expert's final volume, in %
  dE_meV_atom      E0/atom (agent) - E0/atom (expert). Confounded by POTCAR,
                   DFT+U and smearing choices (see relax_new.xlsx notes); report
                   it next to those columns, never alone.

A run that has not ended (no run_meta.json) is still collected -- the files are
there -- but carries status "running"; rep_spread.py refuses such rows.

Usage: collect_results.py [--reps rep1,rep2,rep3] > audit/results.json
       (also writes audit/results.csv)
"""
from __future__ import annotations

import csv
import json
import re
import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

warnings.filterwarnings("ignore")
from pymatgen.analysis.structure_matcher import StructureMatcher  # noqa: E402
from pymatgen.core import Structure  # noqa: E402

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
from check_flow import check, read_incar  # noqa: E402

INCAR_KEYS = ["ENCUT", "KSPACING", "KGAMMA", "PREC", "ISMEAR", "SIGMA", "ISPIN", "MAGMOM",
              "LDAU", "LDAUU", "IVDW", "ISIF", "IBRION", "EDIFF", "EDIFFG", "NSW", "GGA", "METAGGA"]


def e0_of(d: Path):
    last = None
    try:
        for _, elem in ET.iterparse(d / "vasprun.xml", events=("end",)):
            if elem.tag == "calculation":
                energy = elem.find("energy")
                for child in (list(energy) if energy is not None else []):
                    if child.attrib.get("name") == "e_0_energy":
                        last = float(child.text)
                elem.clear()
    except (OSError, ET.ParseError):
        pass
    if last is None and (d / "OSZICAR").exists():
        for line in (d / "OSZICAR").read_text(errors="replace").splitlines():
            m = re.search(r"E0=\s*([-+0-9.Ee]+)", line)
            if m:
                last = float(m.group(1))
    return last


def potcar_titles(d: Path) -> list[str]:
    out = []
    try:
        for line in (d / "OUTCAR").read_text(errors="replace").splitlines():
            m = re.search(r"POTCAR:\s+(.+)", line)
            if m:
                t = " ".join(m.group(1).split())
                if t not in out:
                    out.append(t)
    except OSError:
        pass
    return out


def kpoints_line(d: Path):
    k = d / "KPOINTS"
    if not k.exists():
        return None
    lines = k.read_text(errors="replace").splitlines()
    return " | ".join(x.strip() for x in lines[1:4])


def main() -> None:
    reps = None
    if "--reps" in sys.argv:
        reps = sys.argv[sys.argv.index("--reps") + 1].split(",")
    dataset = {r["system"]: r for r in json.loads((EXP / "data" / "dataset.json").read_text())}
    matcher = StructureMatcher(angle_tol=30)
    ref_cache: dict[str, Structure] = {}
    rows = []
    for rep_dir in sorted((EXP / "runs_agent").iterdir()):
        if not rep_dir.is_dir() or rep_dir.name.startswith(".") or (reps and rep_dir.name not in reps):
            continue
        for ws in sorted(rep_dir.iterdir()):
            if not ws.is_dir() or ws.name.startswith(".") or ws.name not in dataset:
                continue
            system = ws.name
            meta_p = ws / "run_meta.json"
            meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
            flow = check(str(ws))
            row = {
                "rep": rep_dir.name,
                "system": system,
                "status": meta.get("status", "running"),
                "verdict": flow["verdict"],
                "model": meta.get("model"),
                "llm_mode": meta.get("llm_mode"),
                "wall_h": round(meta["wall_seconds"] / 3600, 3) if "wall_seconds" in meta else None,
                "rounds": meta.get("rounds"),
                "total_turns": meta.get("total_turns"),
                "n_qa": len(meta.get("qa", [])),
                "qa_categories": ";".join(q["category"] for q in meta.get("qa", [])),
                "qa_answered_by": ";".join(q["answered_by"] for q in meta.get("qa", [])),
                "n_relax_runs": flow["n_relax_runs"],
                "n_static_runs": flow["n_static_runs"],
                "convergence_report": flow["convergence_report"],
                "flow_notes": " | ".join(flow["notes"]),
            }
            final = flow["final"]
            if final:
                d = ws / final["dir"]
                incar = read_incar(d / "INCAR")
                row.update({
                    "final_dir": final["dir"],
                    "ionic_steps": final["ionic_steps"],
                    **{f"incar_{k}": incar.get(k) for k in INCAR_KEYS},
                    "kpoints": kpoints_line(d),
                    "potcar": "; ".join(potcar_titles(d)),
                })
                try:
                    s = Structure.from_file(d / "CONTCAR")
                    ref = ref_cache.setdefault(system, Structure.from_file(EXP / "reference" / system / "CONTCAR"))
                    rms = matcher.get_rms_dist(s, ref)
                    e0 = e0_of(d)
                    ds = dataset[system]
                    row.update({
                        "natoms": len(s),
                        "volume_A3": round(s.volume, 4),
                        "dV_pct": round(100 * (s.volume / ref.volume - 1), 4),
                        "rmsd_vs_expert": round(rms[0], 6) if rms else None,
                        "e0_eV": e0,
                        "e0_per_atom_eV": e0 / len(s) if e0 is not None else None,
                        "dE_meV_atom": round(1000 * (e0 / len(s) - ds["reference_e0_per_atom_eV"]), 3)
                        if e0 is not None else None,
                        "lattice_abc": [round(x, 5) for x in s.lattice.abc],
                        "lattice_angles": [round(x, 3) for x in s.lattice.angles],
                    })
                except Exception as exc:  # noqa: BLE001 -- recorded per row
                    row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)

    print(json.dumps(rows, indent=2, ensure_ascii=False))
    out_csv = EXP / "audit" / ("results.csv" if not reps else f"results_{'_'.join(reps)}.csv")
    out_csv.parent.mkdir(exist_ok=True)
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()})
    print(f"# wrote {out_csv} ({len(rows)} rows)", file=sys.stderr)


if __name__ == "__main__":
    main()
