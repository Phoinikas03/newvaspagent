#!/usr/bin/env python3
"""Collect both arms into one comparison table.

Two things worth knowing about the numbers:

* `fit_eos.py` reports `a_eq_A` as the *primitive* lattice vector length, not the
  cubic lattice constant. Everything here is converted to the conventional cubic
  constant from the equilibrium volume, which is unambiguous for all three
  structure types in Sol27LC.
* atomate2's EOS postprocessing returns energies and volumes; the equilibrium
  volume is refitted here with the same Birch-Murnaghan form the agent's
  `fit_eos.py` uses, so the two arms are not separated by the fitting code.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
import sys

import numpy as np
from scipy.optimize import curve_fit

EXP = "/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc"
ATOMS_PER_CONVENTIONAL = {"fcc": 4, "dia": 8, "bcc": 2}


def birch_murnaghan(V, E0, V0, B0, B0p):
    eta = (V0 / V) ** (2.0 / 3.0)
    return E0 + 9.0 * V0 * B0 / 16.0 * ((eta - 1) ** 3 * B0p + (eta - 1) ** 2 * (6 - 4 * eta))


def fit_bm(volumes, energies):
    V = np.asarray(volumes, float)
    E = np.asarray(energies, float)
    if len(V) < 4:
        return None
    order = np.argsort(V)
    V, E = V[order], E[order]
    guess = [E.min(), V[len(V) // 2], 1.0, 4.0]
    try:
        popt, _ = curve_fit(birch_murnaghan, V, E, p0=guess, maxfev=20000)
    except (RuntimeError, ValueError):
        return None
    resid = E - birch_murnaghan(V, *popt)
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((E - E.mean()) ** 2))
    return {
        "V0": float(popt[1]),
        "E0": float(popt[0]),
        "B0_GPa": float(popt[2] * 160.21766208),
        "R2": 1 - ss_res / ss_tot if ss_tot else float("nan"),
        "n_points": int(len(V)),
    }


def conventional_a(V0: float, natoms: int, structure_type: str) -> float:
    return (V0 * ATOMS_PER_CONVENTIONAL[structure_type] / natoms) ** (1 / 3)


def natoms_of(system: str) -> int:
    poscar = os.path.join(EXP, "data", system, "POSCAR")
    lines = open(poscar).read().split("\n")
    return sum(int(x) for x in lines[6].split())


def _read_maybe_gz(path: str) -> str:
    if os.path.exists(path):
        return open(path, errors="replace").read()
    if os.path.exists(path + ".gz"):
        return gzip.open(path + ".gz", "rt", errors="replace").read()
    return ""


def agent_result(system: str, rep: str) -> dict:
    """Refit the agent's own volume points with the same Birch-Murnaghan code
    used for atomate2.

    Deliberately not read from whatever `eos_results.json` the agent happened to
    write: one run reported its lattice constant only in a Markdown report, and
    another's JSON was produced after the operator asked for it. Refitting both
    arms from OUTCARs puts them through identical fitting code and removes any
    dependence on the agent emitting a particular artifact.
    """
    root = os.path.join(EXP, "runs_agent", rep, system)
    out = {"arm": f"agent/{rep}", "system": system}
    if not os.path.isdir(root):
        return {}

    volumes, energies, encuts, dirs = [], [], set(), []
    for d in sorted(glob.glob(os.path.join(root, "**", "scale_*"), recursive=True)):
        if not os.path.isdir(d) or "convergence" in d:
            continue
        outcar = _read_maybe_gz(os.path.join(d, "OUTCAR"))
        if not outcar:
            continue
        vol = re.findall(r"volume of cell :\s+([\d.]+)", outcar)
        ene = re.findall(r"energy\(sigma->0\)\s*=\s*(-?[\d.]+)", outcar)
        if not (vol and ene):
            continue
        volumes.append(float(vol[-1]))
        energies.append(float(ene[-1]))
        dirs.append(os.path.basename(d))
        m = re.search(r"ENCUT\s*=\s*([\d.]+)", outcar)
        if m:
            encuts.add(round(float(m.group(1)), 1))

    if volumes:
        # Duplicate volumes appear when a refinement round re-runs a point.
        seen = {}
        for v, e in zip(volumes, energies):
            seen[round(v, 4)] = e
        vs = sorted(seen)
        fit = fit_bm(vs, [seen[v] for v in vs])
        out["n_points"] = len(vs)
        if fit:
            out.update(V0=fit["V0"], B0_GPa=fit["B0_GPa"], R2=fit["R2"], n_points=fit["n_points"])
        if len(encuts) > 1:
            out["encut_inconsistent"] = sorted(encuts)

    meta_path = os.path.join(root, "run_meta.json")
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path))
        out.update(status=meta.get("status"), wall_s=meta.get("wall_seconds"),
                   rounds=meta.get("rounds"), turns=meta.get("total_turns"),
                   qa=len(meta.get("qa", [])), model=meta.get("model"),
                   llm_mode=meta.get("llm_mode"))

    incars = sorted(glob.glob(os.path.join(root, "**", "scale_1.0*", "INCAR"), recursive=True))
    if incars:
        text = open(incars[0]).read()
        for key in ("ENCUT", "KSPACING", "ISMEAR", "SIGMA", "EDIFF"):
            m = re.search(rf"^\s*{key}\s*=\s*([^\s#!]+)", text, re.M)
            if m:
                out[key] = m.group(1)
    return out


def atomate2_result(system: str) -> dict:
    root = os.path.join(EXP, "runs_atomate2", system)
    out = {"arm": "atomate2", "system": system}
    if not os.path.isdir(root):
        return {}
    meta_path = os.path.join(root, "run_meta.json")
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path))
        out.update(status=meta.get("status"), wall_s=meta.get("wall_seconds"))

    volumes, energies = [], []
    for job in sorted(glob.glob(os.path.join(root, "job_*"))):
        xml = os.path.join(job, "vasprun.xml")
        if not (os.path.exists(xml) or os.path.exists(xml + ".gz")):
            continue
        incar = _read_maybe_gz(os.path.join(job, "INCAR"))
        if "NSW" in incar and not re.search(r"^\s*NSW\s*=\s*0\b", incar, re.M):
            continue  # keep the statics, drop the relaxations
        outcar = _read_maybe_gz(os.path.join(job, "OUTCAR"))
        vol = re.findall(r"volume of cell :\s+([\d.]+)", outcar)
        ene = re.findall(r"energy\(sigma->0\)\s*=\s*(-?[\d.]+)", outcar)
        if vol and ene:
            volumes.append(float(vol[-1]))
            energies.append(float(ene[-1]))
    if volumes:
        out["n_points"] = len(volumes)
        fit = fit_bm(volumes, energies)
        if fit:
            out.update(V0=fit["V0"], B0_GPa=fit["B0_GPa"], R2=fit["R2"], n_points=fit["n_points"])

    # custodian corrections actually applied
    events = []
    for cj in glob.glob(os.path.join(root, "job_*", "custodian.json*")):
        try:
            raw = gzip.open(cj, "rt").read() if cj.endswith(".gz") else open(cj).read()
            for entry in json.loads(raw):
                for corr in entry.get("corrections", []):
                    handler = corr.get("handler")
                    if isinstance(handler, dict):
                        handler = handler.get("@class") or handler.get("name")
                    events.append(str(handler or corr.get("errors")))
        except (OSError, ValueError):
            continue
    log = os.path.join(EXP, "runs_atomate2", f"{system}.log")
    if os.path.exists(log):
        events += re.findall(r"ERROR:custodian\.custodian:(\w+)", open(log, errors="replace").read())
    out["custodian_events"] = len(events)
    out["custodian_handlers"] = ",".join(sorted(set(e for e in events if e))) or "-"
    return out


def main() -> None:
    systems = sorted(d for d in os.listdir(os.path.join(EXP, "data")) if not d.endswith(".json"))
    reps = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(EXP, "runs_agent", "*")))
            if os.path.isdir(p)]
    rows = []
    for s in systems:
        st = s.split("_")[1]
        n = natoms_of(s)
        for r in reps:
            res = agent_result(s, r)
            if res:
                if res.get("V0"):
                    res["a_conv_A"] = conventional_a(res["V0"], n, st)
                rows.append(res)
        res = atomate2_result(s)
        if res:
            if res.get("V0"):
                res["a_conv_A"] = conventional_a(res["V0"], n, st)
            rows.append(res)

    with open(os.path.join(EXP, "audit", "results.json"), "w") as fh:
        json.dump(rows, fh, indent=2)

    hdr = (f"{'system':<9} {'arm':<14} {'status':<12} {'a_conv':>8} {'B0':>7} "
           f"{'R2':>9} {'pts':>4} {'wall_s':>8} {'ENCUT':>7} {'KSPC':>6} {'cust':>5}")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        a = f"{r['a_conv_A']:.4f}" if r.get("a_conv_A") else "-"
        b = f"{r['B0_GPa']:.1f}" if r.get("B0_GPa") else "-"
        r2 = f"{r['R2']:.6f}" if isinstance(r.get("R2"), float) else "-"
        print(f"{r['system']:<9} {r['arm']:<14} {str(r.get('status','-')):<12} {a:>8} {b:>7} "
              f"{r2:>9} {str(r.get('n_points','-')):>4} {str(r.get('wall_s','-')):>8} "
              f"{str(r.get('ENCUT','-')):>7} {str(r.get('KSPACING','-')):>6} "
              f"{str(r.get('custodian_events','-')):>5}")


if __name__ == "__main__":
    main()
