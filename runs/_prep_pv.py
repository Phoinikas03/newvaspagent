#!/usr/bin/env python3
"""Prepare pv/sv/_d-pseudopotential re-runs of selected rx_* relaxations.

For each system: copy the ORIGINAL input POSCAR and the rx_* INCAR into a new
rxpv_* directory, adjust parallel params for single-GPU (KPAR=1, drop NCORE/NPAR),
and build POTCAR by concatenating the MPRelaxSet-recommended semicore variants
(in POSCAR species order).
"""
import os
import shutil
from pathlib import Path

RUNS = Path("/home/xiazeyu21/newvaspagent/runs")
POT = Path("/home/xiazeyu21/newvaspagent/POTCAR_dir/POT_GGA_PAW_PBE")

# system -> (source rx dir, list of POTCAR variant symbols in POSCAR species order)
SYSTEMS = {
    "BaTiO3":    ("rx_BaTiO3",        ["Ba_sv", "Ti_pv", "O"]),
    "BaFeO3":    ("rx_BaFeO3",        ["Ba_sv", "Fe_pv", "O"]),
    "FeSe":      ("rx_FeSe",          ["Fe_pv", "Se"]),
    "LiCoO2":    ("rx_LiCoO2",        ["Li_sv", "Co", "O"]),
    "LiFePO4":   ("rx_LiFePO4",       ["Li_sv", "Fe_pv", "P", "O"]),
    "LiMn2O4":   ("rx_LiMn2O4/relax", ["Li_sv", "Mn_pv", "O"]),
    "TiPbO3":    ("rx_TiPbO3",        ["Ti_pv", "Pb_d", "O"]),
    "Li4Ti5O12": ("rx_Li4Ti5O12",     ["Li_sv", "Ti_pv", "O"]),
    "SnSe":      ("rx_SnSe",          ["Sn_d", "Se"]),
    "CaF2":      ("rx_CaF2",          ["Ca_sv", "F"]),
    "NaCl":      ("rx_NaCl",          ["Na_pv", "Cl"]),
}

DROP_KEYS = {"NCORE", "NPAR"}


def fix_incar(text: str) -> str:
    out = []
    saw_kpar = False
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip().upper() if "=" in line else ""
        if key in DROP_KEYS:
            continue
        if key == "KPAR":
            out.append("KPAR = 1")
            saw_kpar = True
            continue
        out.append(line)
    if not saw_kpar:
        out.append("KPAR = 1")
    return "\n".join(out) + "\n"


def species_from_poscar(poscar: Path):
    lines = poscar.read_text().splitlines()
    return lines[5].split()


def main():
    for name, (src_rel, pot_syms) in SYSTEMS.items():
        src = RUNS / src_rel
        dst = RUNS / f"rxpv_{name}"
        dst.mkdir(parents=True, exist_ok=True)

        # POSCAR (original input) + INCAR
        shutil.copy(src / "POSCAR", dst / "POSCAR")
        incar_txt = (src / "INCAR").read_text()
        (dst / "INCAR").write_text(fix_incar(incar_txt))

        # sanity: POTCAR variant count must equal number of species in POSCAR
        sp = species_from_poscar(dst / "POSCAR")
        assert len(sp) == len(pot_syms), f"{name}: species {sp} vs pots {pot_syms}"

        # build POTCAR by concatenation in species order
        with open(dst / "POTCAR", "wb") as fout:
            for psym in pot_syms:
                pfile = POT / psym / "POTCAR"
                if not pfile.exists():
                    raise FileNotFoundError(f"missing {pfile}")
                fout.write(pfile.read_bytes())

        # report TITELs actually written
        titels = []
        for ln in (dst / "POTCAR").read_text(errors="ignore").splitlines():
            if "TITEL" in ln:
                titels.append(ln.split("=", 1)[1].strip())
        print(f"{name:10s} <- {src_rel:18s} species={sp} pots={pot_syms}")
        print(f"            TITEL: {titels}")


if __name__ == "__main__":
    main()
