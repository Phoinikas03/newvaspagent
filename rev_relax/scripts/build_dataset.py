#!/usr/bin/env python
"""Freeze the SR (structure relaxation) input set and expert references.

Inputs are the 40 starting structures of the manuscript's SR task
(``<repo>/data/relax/<MAT>``, a POSCAR each) -- La2CuO4 is left out because
its expert relaxation never reached ionic convergence, as in relax_new.xlsx.
They are copied byte-for-byte; no symmetrisation or cell reduction, so every
rep starts from exactly the structure the manuscript's runs started from.

The expert reference of each system is the final structure of the benchmark
relaxation under ``vasp_benchmark_old/relax/<MAT>/relax`` (Cr: the 2026-06-25
reference re-run, the same choice as scripts/rebuild_relax_new_current.py).
Only CONTCAR, INCAR and KPOINTS are copied, plus the final E0 and the POTCAR
titles in reference.json -- never a POTCAR.

Run on d01 only (the sources are not on d03). data/ is committed; reference/
is NOT (see .gitignore): the agent works under rev_relax/runs_agent and in the
first pilot listed rev_relax/reference/ on its own. Whatever sits in the
repository on the run machine is within the agent's reach, so the expert
answers never go there; RMSD vs expert is computed on d01 after the runs come
back.
"""
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from pymatgen.core import Structure
from pymatgen.io.vasp import Poscar
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parent
SRC = REPO / "data" / "relax"
REF_ROOT = REPO.parent / "vasp_benchmark_old" / "relax"
EXCLUDE = {"La2CuO4"}
# Parentheses in a directory name break unquoted shell commands; the agent
# would pay for that in rounds, so the workspace uses the conventional formula.
RENAME = {"Li10Ge(PS6)2": "Li10GeP2S12"}


def ref_dir(material: str) -> Path:
    if material == "Cr":
        return REF_ROOT / material / "relax_cr35_reference_rerun_20260625"
    return REF_ROOT / material / "relax"


def final_e0(directory: Path):
    last = None
    try:
        for _, elem in ET.iterparse(directory / "vasprun.xml", events=("end",)):
            if elem.tag == "calculation":
                energy = elem.find("energy")
                for child in (list(energy) if energy is not None else []):
                    if child.attrib.get("name") == "e_0_energy":
                        last = float(child.text)
                elem.clear()
    except (OSError, ET.ParseError):
        pass
    if last is None:
        for line in (directory / "OSZICAR").read_text(errors="replace").splitlines():
            m = re.search(r"E0=\s*([-+0-9.Ee]+)", line)
            if m:
                last = float(m.group(1))
    return last


def potcar_titles(directory: Path) -> list[str]:
    titles = []
    for line in (directory / "OUTCAR").read_text(errors="replace").splitlines():
        m = re.search(r"POTCAR:\s+(.+)", line)
        if m:
            t = " ".join(m.group(1).split())
            if t not in titles:
                titles.append(t)
    return titles


def main() -> None:
    rows, refs = [], []
    for src in sorted(SRC.iterdir()):
        mat = src.name
        if mat in EXCLUDE:
            continue
        system = RENAME.get(mat, mat)
        rdir = ref_dir(mat)
        outcar = (rdir / "OUTCAR").read_text(errors="replace")
        if "reached required accuracy" not in outcar:
            sys.exit(f"{mat}: expert reference not ionically converged ({rdir})")

        (EXP / "data" / system).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, EXP / "data" / system / "POSCAR")
        (EXP / "reference" / system).mkdir(parents=True, exist_ok=True)
        for name in ("CONTCAR", "INCAR", "KPOINTS"):
            if (rdir / name).exists():
                shutil.copyfile(rdir / name, EXP / "reference" / system / name)

        s0 = Poscar.from_file(src, check_for_potcar=False).structure
        sref = Structure.from_file(rdir / "CONTCAR")
        e0 = final_e0(rdir)
        rows.append({
            "system": system,
            "source_name": mat,
            "source": f"data/relax/{mat}",
            "poscar_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
            "formula": s0.composition.formula.replace(" ", ""),
            "natoms": len(s0),
            "spacegroup_initial": SpacegroupAnalyzer(s0, symprec=0.1).get_space_group_symbol(),
            "volume_initial_A3": round(s0.volume, 4),
        })
        refs.append({
            "system": system,
            "reference_dir": str(rdir.relative_to(REPO.parent)),
            "reference_e0_eV": e0,
            "reference_e0_per_atom_eV": e0 / len(sref) if e0 is not None else None,
            "reference_natoms": len(sref),
            "reference_volume_A3": round(sref.volume, 4),
            "reference_potcar": potcar_titles(rdir),
        })
        print(f"{system:<14} nat={len(s0):<3} V0={s0.volume:8.2f} Vref={sref.volume:8.2f} E0ref={e0}")

    (EXP / "data" / "dataset.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    (EXP / "reference" / "reference.json").write_text(json.dumps(refs, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(rows)} systems")


if __name__ == "__main__":
    main()
