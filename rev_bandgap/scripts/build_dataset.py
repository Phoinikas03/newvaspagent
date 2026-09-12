#!/usr/bin/env python
"""Assemble the five-material band-gap pilot input set.

Structures are taken from the directory that actually ran the HSE calculation,
not from the run-directory root: in the Sol27LC set several root POSCARs had
been overwritten after the fact and no longer matched the element that was
computed. Composition is checked against the material name before a structure
is accepted.
"""
import json
import os

from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

RUNS = "/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/runs"
OUT = "/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap/data"

# material -> (source POSCAR relative to runs/bg_<material>, expected composition)
PILOT = {
    "Si":     ("hse_scf/POSCAR",  {"Si": 2}),
    "GaAs":   ("hse_scf/POSCAR",  {"Ga": 1, "As": 1}),
    "ZnO":    ("POSCAR",          {"Zn": 2, "O": 2}),
    "Cu2O":   ("hse_calc/POSCAR", {"Cu": 4, "O": 2}),
    # Ga2O3 (10 atoms) was dropped from the pilot: at the cutoff and single-GPU
    # layout the agent consistently chooses, it would not finish inside the budget.
    # GaP replaces it -- same III-V family as GaAs but with an indirect gap, so it
    # also checks that the workflow reports the gap type correctly.
    "GaP":    ("hse_scf/POSCAR",  {"Ga": 1, "P": 1}),
}


def main() -> None:
    rows = []
    for material, (rel, expected) in PILOT.items():
        src = os.path.join(RUNS, f"bg_{material}", rel)
        structure = Structure.from_file(src)
        got = {str(el): int(n) for el, n in structure.composition.get_el_amt_dict().items()}
        assert got == expected, f"{material}: expected {expected}, found {got} in {src}"

        sga = SpacegroupAnalyzer(structure, symprec=1e-3)
        primitive = sga.get_primitive_standard_structure()
        # keep whichever cell is smaller; these are already primitive in most cases
        chosen = primitive if len(primitive) <= len(structure) else structure

        dest = os.path.join(OUT, material)
        os.makedirs(dest, exist_ok=True)
        chosen.to(filename=os.path.join(dest, "POSCAR"), fmt="poscar")
        rows.append({
            "material": material,
            "source": os.path.relpath(src, RUNS),
            "natoms_source": len(structure),
            "natoms_used": len(chosen),
            "spacegroup": sga.get_space_group_symbol(),
            "volume_A3": round(chosen.volume, 4),
            "formula": chosen.composition.reduced_formula,
        })

    with open(os.path.join(OUT, "dataset.json"), "w") as fh:
        json.dump(rows, fh, indent=2)
    print(f"{'material':<8} {'formula':<8} {'src N':>6} {'used N':>7} {'spacegroup':>12} {'V(A^3)':>10}")
    for r in rows:
        print(f"{r['material']:<8} {r['formula']:<8} {r['natoms_source']:>6} {r['natoms_used']:>7} "
              f"{r['spacegroup']:>12} {r['volume_A3']:>10.3f}")


if __name__ == "__main__":
    main()
