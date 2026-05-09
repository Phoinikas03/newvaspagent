# Convergence Report for FCC Ca

## 1. ENCUT Convergence (KSPACING=0.15)
| ENCUT (eV) | Total Energy (eV) | ΔE (meV/atom) |
| :--- | :--- | :--- |
| 250 | -1.91778038 | - |
| 300 | -1.91780960 | -0.02922 |
| 350 | -1.91793046 | -0.12086 |
| 400 | -1.91800405 | -0.07359 |
| 450 | -1.91801020 | -0.00615 |

**Selected ENCUT: 400 eV** (Convergence < 1 meV/atom reached at 300 eV, but 400 eV is chosen for higher accuracy).

## 2. KSPACING Convergence (ENCUT=400 eV)
| KSPACING | Total Energy (eV) | ΔE (meV/atom) |
| :--- | :--- | :--- |
| 0.30 | -1.92281886 | - |
| 0.25 | -1.91512115 | 7.69771 |
| 0.20 | -1.91918982 | -4.06867 |
| 0.15 | -1.91800405 | 1.18577 |
| 0.12 | -1.91724102 | 0.76303 |

**Selected KSPACING: 0.12** (Convergence < 1 meV/atom reached at 0.12).

## Final Parameters for EOS:
- **ENCUT = 400 eV**
- **KSPACING = 0.12**
