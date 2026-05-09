# Convergence Report — Pd FCC

**POSCAR 来源**: Materials Project mp-2 (Pd FCC 原始胞, 1 atom)
**VASP 版本**: 6.4.2 (GPU build, vasp_std)
**ISMEAR/SIGMA**: 1 / 0.1 (Methfessel-Paxton, 金属)
**PREC**: Accurate, NSW=0 (静态单点)

---

## ENCUT 收敛测试 (KSPACING=0.15 固定)

| ENCUT (eV) | E (eV/atom) | ΔE (meV/atom) |
|---|---|---|
| 250 | -5.20946527 | — |
| 300 | -5.21674507 | -7.28 |
| 350 | -5.21185602 | +4.89 |
| 400 | -5.21168030 | **+0.18** ✓ |
| 450 | -5.21183826 | -0.16 ✓ |
| 500 | -5.21192881 | -0.09 ✓ |

**收敛判定**: 350→400 eV 时 |ΔE| = 0.18 meV/atom ≤ 1 meV/atom
**推荐 ENCUT**: **400 eV**

---

## KSPACING 收敛测试 (ENCUT=400 eV 固定)

| KSPACING (Å⁻¹) | E (eV/atom) | ΔE (meV/atom) |
|---|---|---|
| 0.30 | -5.22716072 | — |
| 0.25 | -5.21676746 | +10.39 |
| 0.20 | -5.20284732 | +13.92 |
| 0.15 | -5.21168030 | -8.83 |
| 0.10 | -5.21173874 | **-0.06** ✓ |

**收敛判定**: 0.15→0.10 时 |ΔE| = 0.06 meV/atom ≤ 1 meV/atom
**推荐 KSPACING**: **0.10 Å⁻¹**

---

## 推荐生产参数

| 参数 | 值 |
|---|---|
| ENCUT | 400 eV |
| KSPACING | 0.10 Å⁻¹ |
| KGAMMA | .TRUE. |
| ISMEAR | 1 |
| SIGMA | 0.1 eV |

> 后续所有 EOS scale_* 静态计算须使用相同 ENCUT/KSPACING/POTCAR，不得混用。
