# INCAR Parameters for AlN Relaxation
- **ENCUT = 520**: 1.3 times the ENMAX of Nitrogen (400 eV) to eliminate Pulay stress during volume relaxation.
- **EDIFF = 1E-6**: Standard precision for electronic steps.
- **EDIFFG = -0.01**: Convergence criteria based on forces, ensuring a stable ground state geometry.
- **NSW = 200**: Sufficient steps for initial relaxation.
- **IBRION = 2**: Conjugate gradient algorithm is robust for starting structures.
- **ISIF = 3**: Full relaxation of atomic positions and lattice parameters.
- **ISMEAR = 0, SIGMA = 0.05**: Gaussian smearing is appropriate for the wide-gap semiconductor AlN.
- **KSPACING = 0.25**: Moderate K-point density, suitable for initial relaxation.
