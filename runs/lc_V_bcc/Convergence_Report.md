# V BCC Convergence Report

## ENCUT Convergence (Fixed KSPACING = 0.15)
| ENCUT (eV) | Total Energy (eV) | ΔE (meV/atom) |
|------------|-------------------|---------------|
| 250        | -8.94553636       | -             |
| 300        | -8.94199040       | 3.55          |
| 350        | -8.94135415       | 0.64          |
| 400        | -8.94135529       | 0.00          |

**Selected ENCUT: 350 eV** (Stability achieved at 350 eV).

## KSPACING Convergence (Fixed ENCUT = 400 eV)
| KSPACING (1/A) | Total Energy (eV) | ΔE (meV/atom) |
|----------------|-------------------|---------------|
| 0.25           | -8.93204801       | -             |
| 0.20           | -8.94489399       | -12.85        |
| 0.15           | -8.94135529       | 3.54          |
| 0.12           | -8.94151534       | -0.16         |

**Selected KSPACING: 0.15 1/A**.

## Production Parameters
- ENCUT: 350 eV
- KSPACING: 0.15 1/A
- ISMEAR: 1
- SIGMA: 0.05
