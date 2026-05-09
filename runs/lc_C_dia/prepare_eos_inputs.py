#!/usr/bin/env python3
"""Prepare INCAR and POTCAR for each scale directory."""

import os
import shutil

# INCAR template for static calculation (EOS)
incar_template = """! EOS calculation for diamond C
! Static calculation (NSW=0)

SYSTEM = Diamond C - EOS

! Electronic relaxation
ENCUT = 500
ISMEAR = 0
SIGMA = 0.05
NELM = 100
EDIFF = 1e-6

! Static calculation (no ionic relaxation)
NSW = 0
ISIF = 2

! K-point spacing (from convergence test)
KSPACING = 0.15
KGAMMA = .TRUE.

! Output
LWAVE = .FALSE.
LCHARG = .FALSE.
LELF = .FALSE.
"""

# Find all scale_* directories
scale_dirs = sorted([d for d in os.listdir('.') if d.startswith('scale_')])

for scale_dir in scale_dirs:
    # Write INCAR
    incar_path = os.path.join(scale_dir, 'INCAR')
    with open(incar_path, 'w') as f:
        f.write(incar_template)

    # Copy POTCAR
    potcar_src = 'POTCAR'
    potcar_dst = os.path.join(scale_dir, 'POTCAR')
    if os.path.exists(potcar_src):
        shutil.copy(potcar_src, potcar_dst)

    print(f"Prepared {scale_dir}: INCAR and POTCAR")

print(f"\nTotal {len(scale_dirs)} scale directories prepared.")
