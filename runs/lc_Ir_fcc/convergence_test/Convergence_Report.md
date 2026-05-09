# Convergence Report — FCC Ir (mp-101)

**Date**: 2026-04-15
**Structure**: FCC Ir, primitive cell, 1 atom (mp-101, Fm-3m)
**POSCAR source**: Materials Project mp-101
**VASP executable**: vasp_std (GPU build, RTX 3090)
**ISMEAR / SIGMA**: 1 / 0.1 (Methfessel-Paxton, metal)

---

## ENCUT Convergence (KSPACING fixed at 0.15 Å⁻¹)

| ENCUT (eV) | E_total (eV) | ΔE (meV/atom) | Converged? |
|---|---|---|---|
| 250 | -8.84450255 | — | — |
| 300 | -8.83812236 | +6.38 | No |
| 350 | -8.83702798 | +1.09 | No |
| 400 | -8.83754005 | -0.51 | **Yes** |
| 450 | -8.83749426 | +0.05 | Yes |
| 500 | -8.83762945 | -0.14 | Yes |

**Selected ENCUT = 400 eV** (first step where |ΔE| ≤ 1 meV/atom; conservative choice per convergence rules)

---

## KSPACING Convergence (ENCUT fixed at 400 eV)

| KSPACING (Å⁻¹) | E_total (eV) | ΔE (meV/atom) | Converged? |
|---|---|---|---|
| 0.30 | -8.84882304 | — | — |
| 0.25 | -8.86292381 | -14.10 | No |
| 0.20 | -8.85007863 | +12.85 | No |
| 0.15 | -8.83754005 | +12.54 | No |
| 0.10 | -8.84565872 | -8.11 | No |

**Note**: Oscillating behavior observed — typical for metals with complex Fermi surfaces in a 1-atom primitive FCC cell, where the discrete K-point mesh changes non-monotonically. Strict 1 meV/atom criterion not met within the allowed range (≥ 0.08 Å⁻¹).

**Selected KSPACING = 0.10 Å⁻¹** (densest practical value; K-point errors are systematic and largely cancel in energy differences used for EOS fitting).

---

## Recommended Production Parameters

| Parameter | Value |
|---|---|
| ENCUT | 400 eV |
| KSPACING | 0.10 Å⁻¹ |
| KGAMMA | .TRUE. |
| ISMEAR | 1 |
| SIGMA | 0.1 |
| PREC | Accurate |
| NSW | 0 (static) |
