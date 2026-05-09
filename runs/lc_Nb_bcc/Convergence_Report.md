# Convergence Report: BCC Nb

## ENCUT Convergence (Fixed KSPACING=0.15)
| ENCUT (eV) | Total Energy (eV) | ΔE (meV/atom) |
|------------|-------------------|---------------|
| 250        | -10.06764712      | -             |
| 300        | -10.08361211      | -15.96        |
| 350        | -10.09023219      | -6.62         |
| 400        | -10.09097502      | -0.74         |
| 450        | -10.09118802      | -0.21         |
| 500        | -10.09201862      | -0.83         |
| 550        | -10.09260049      | -0.58         |

**Decision**: ENCUT = 500 eV (Energy difference < 1 meV/atom starting from 400 eV).

## KSPACING Convergence (Fixed ENCUT=500 eV)
| KSPACING (Å⁻¹) | Total Energy (eV) | ΔE (meV/atom) |
|----------------|-------------------|---------------|
| 0.30           | -10.10281935      | -             |
| 0.25           | -10.08417088      | +18.65        |
| 0.20           | -10.08863683      | -4.47         |
| 0.15           | -10.09201862      | -3.38         |
| 0.10           | -10.09198719      | +0.03         |

**Decision**: KSPACING = 0.10 Å⁻¹ (Converged to 0.03 meV/atom relative to 0.15 Å⁻¹).
Actually, 0.15 is also quite good (3.4 meV/atom), but 0.10 is very safe. I will use **KSPACING = 0.10**.
