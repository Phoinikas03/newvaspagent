#!/usr/bin/env python3
"""Generate INCAR files for ENCUT convergence test."""

import os

# ENCUT values to test
encut_values = [250, 300, 350, 400, 450, 500]

# Base INCAR template
incar_template = """! ENCUT convergence test for diamond C
! Static calculation (NSW=0)

SYSTEM = Diamond C - ENCUT Test

! Electronic relaxation
ENCUT = {encut}
ISMEAR = 0
SIGMA = 0.05
NELM = 100
EDIFF = 1e-6

! Static calculation
NSW = 0
ISIF = 2

! K-point spacing (fixed at dense value for ENCUT test)
KSPACING = 0.15
KGAMMA = .TRUE.

! Output
LWAVE = .FALSE.
LCHARG = .FALSE.
LELF = .FALSE.
"""

# Create ENCUT test directories
for encut in encut_values:
    dirname = f"convergence_test/encut_test/e_{encut}"
    os.makedirs(dirname, exist_ok=True)

    # Write INCAR
    incar_content = incar_template.format(encut=encut)
    with open(f"{dirname}/INCAR", "w") as f:
        f.write(incar_content)

    print(f"Created {dirname}/INCAR with ENCUT={encut}")

print("\nENCAT test directories prepared.")
