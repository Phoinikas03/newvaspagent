#!/usr/bin/env python3
"""Generate INCAR files for KSPACING convergence test (Ag metal)."""

import os

# KSPACING values to test
kspacing_values = [0.30, 0.25, 0.20, 0.15, 0.10]

# Base INCAR template
incar_template = """! KSPACING convergence test for FCC Ag
! Static calculation (NSW=0)

SYSTEM = FCC Ag - KSPACING Test

! Electronic relaxation (metal)
ENCUT = 400
ISMEAR = 1
SIGMA = 0.1
NELM = 100
EDIFF = 1e-6

! Static calculation
NSW = 0
ISIF = 2

! K-point spacing (variable)
KSPACING = {kspacing}
KGAMMA = .TRUE.

! Output
LWAVE = .FALSE.
LCHARG = .FALSE.
LELF = .FALSE.
"""

# Create KSPACING test directories
for kspacing in kspacing_values:
    dirname = f"convergence_test/kspacing_test/k_{kspacing:.2f}"
    os.makedirs(dirname, exist_ok=True)

    # Write INCAR
    incar_content = incar_template.format(kspacing=kspacing)
    with open(f"{dirname}/INCAR", "w") as f:
        f.write(incar_content)

    print(f"Created {dirname}/INCAR with KSPACING={kspacing}")

print("\nKSPACING test directories prepared.")
