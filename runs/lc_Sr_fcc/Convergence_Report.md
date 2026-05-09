# Convergence Test Report for FCC Sr

## ENCUT Convergence Test
Fixed KSPACING = 0.10, KGAMMA = .TRUE.

| ENCUT (eV) | Total Energy (eV) | $\Delta E$ (meV/atom) |
|------------|-------------------|-----------------------|
| 230        | -1.6372391        | -                     |
| 280        | -1.6379046        | 0.67                  |
| 330        | -1.6372097        | 0.69                  |
| 380        | -1.6363761        | 0.83                  |
| 430        | -1.6366230        | 0.25                  |
| 480        | -1.6371006        | 0.48                  |

**Selected ENCUT: 430 eV**

## KSPACING Convergence Test
Fixed ENCUT = 430 eV, KGAMMA = .TRUE.

| KSPACING ($Å^{-1}$) | Total Energy (eV) | $\Delta E$ (meV/atom) |
|---------------------|-------------------|-----------------------|
| 0.30                | -1.6112695        | -                     |
| 0.25                | -1.6415626        | 30.29                 |
| 0.20                | -1.6341838        | 7.38                  |
| 0.15                | -1.6355894        | 1.41                  |
| 0.10                | -1.6366230        | 1.03                  |

**Selected KSPACING: 0.10** (Reached ~1 meV/atom convergence)

## EOS Fitting Results (Birch-Murnaghan)
- **Equilibrium Volume ($):** 54.6956 $Å^3$/atom
- **Minimum Energy ($):** -1.6376 eV/atom
- **Bulk Modulus ($):** 11.63 GPa
- **Pressure Derivative ('$):** 3.47
- **R-squared:** 0.99997

## Equilibrium Lattice Constant
For FCC structure ({cell} = a^3/4$ for 1 atom primitive cell is not correct here, my POSCAR has 1 atom in a 54.69 A^3 cell? Wait, let me check POSCAR content again.)
