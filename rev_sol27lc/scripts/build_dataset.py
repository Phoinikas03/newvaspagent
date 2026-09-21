#!/usr/bin/env python
"""Rebuild the Sol27LC input set for the revision baseline experiment.

The reference structure of each system is recovered from the *production* EOS
run (``scale_1.000/POSCAR``), not from the run-directory root: several root
POSCARs were overwritten after the fact and no longer match the element that
was actually computed (e.g. lc_C_dia/POSCAR is silver).

Every structure is then reduced to the standard primitive cell so that both
arms start from an identical, uniformly-shaped input.
"""
import glob
import json
import os
import re
import sys

from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

_EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.dirname(_EXP), "runs")  # archived manuscript runs (d01 only)
OUT = os.path.join(_EXP, "data")
# atoms per conventional cell, used only to report the cubic lattice constant
PER_CONV = {"fcc": 4, "dia": 8, "bcc": 2}


def reference_poscar(run_dir):
    hits = [
        p
        for p in sorted(glob.glob(os.path.join(run_dir, "**", "scale_1.0*", "POSCAR"), recursive=True))
        if re.search(r"scale_1\.0+0?$", os.path.dirname(p))
    ]
    return hits[0] if hits else None


def main():
    rows = []
    for run_dir in sorted(glob.glob(os.path.join(SRC, "lc_*"))):
        name = os.path.basename(run_dir)
        element, structure_type = name.split("_")[1], name.split("_")[2]
        src = reference_poscar(run_dir)
        if src is None:
            print(f"SKIP {name}: no scale_1.000 POSCAR", file=sys.stderr)
            continue

        original = Structure.from_file(src)
        formula = original.composition.chemical_system
        if formula != element:
            print(f"SKIP {name}: recovered structure is {formula}, expected {element}", file=sys.stderr)
            continue

        primitive = SpacegroupAnalyzer(original, symprec=1e-3).get_primitive_standard_structure()
        a_conv = (primitive.volume * PER_CONV[structure_type] / len(primitive)) ** (1 / 3)

        dest_dir = os.path.join(OUT, f"{element}_{structure_type}")
        os.makedirs(dest_dir, exist_ok=True)
        primitive.to(filename=os.path.join(dest_dir, "POSCAR"), fmt="poscar")

        rows.append(
            {
                "system": f"{element}_{structure_type}",
                "element": element,
                "structure_type": structure_type,
                "source": os.path.relpath(src, SRC),
                "natoms_source": len(original),
                "natoms_primitive": len(primitive),
                "spacegroup": SpacegroupAnalyzer(primitive, symprec=1e-3).get_space_group_symbol(),
                "volume_primitive_A3": round(primitive.volume, 4),
                "a_conventional_A": round(a_conv, 4),
            }
        )

    with open(os.path.join(OUT, "dataset.json"), "w") as fh:
        json.dump(rows, fh, indent=2)

    print(f"{'system':<10} {'src natoms':>10} {'prim natoms':>11} {'spacegroup':>11} {'a_conv(A)':>10}")
    for r in rows:
        print(
            f"{r['system']:<10} {r['natoms_source']:>10} {r['natoms_primitive']:>11} "
            f"{r['spacegroup']:>11} {r['a_conventional_A']:>10.4f}"
        )
    print(f"\n{len(rows)} systems written to {OUT}")


if __name__ == "__main__":
    main()
