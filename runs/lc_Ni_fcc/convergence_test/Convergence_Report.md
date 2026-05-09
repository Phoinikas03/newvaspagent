# Convergence Report — FCC Ni

**结构来源**：Materials Project mp-23（FCC Ni 原胞，1 原子）
**收敛判据**：相邻步 |ΔE| ≤ 1 meV/atom
**VASP 设置**：ISMEAR=1, SIGMA=0.1, ISPIN=2, MAGMOM=1, PREC=Accurate, NSW=0

---

## ENCUT 收敛（固定 KSPACING=0.15 Å⁻¹）

| ENCUT (eV) | E_total (eV) | ΔE (meV/atom) |
|---|---|---|
| 250 | -5.42935 | — |
| 300 | -5.46846 | -39.11 |
| 350 | -5.46420 | +4.26 |
| 400 | -5.45903 | +5.18 |
| 450 | -5.45795 | +1.08 |
| 500 | -5.45805 | **-0.10** ✓ |

**推荐 ENCUT = 500 eV**（450→500 之间 |ΔE| = 0.10 meV/atom）

---

## KSPACING 收敛（固定 ENCUT=500 eV）

| KSPACING (Å⁻¹) | E_total (eV) | ΔE (meV/atom) |
|---|---|---|
| 0.30 | -5.46026 | — |
| 0.25 | -5.46132 | -1.06 |
| 0.20 | -5.45916 | +2.16 |
| 0.15 | -5.45805 | +1.11 |
| 0.10 | -5.45825 | **-0.20** ✓ |

**推荐 KSPACING = 0.10 Å⁻¹**（0.15→0.10 之间 |ΔE| = 0.20 meV/atom）

---

## 推荐生产参数

| 参数 | 值 |
|---|---|
| ENCUT | 500 eV |
| KSPACING | 0.10 Å⁻¹ |
| KGAMMA | .TRUE. |
| ISMEAR | 1 |
| SIGMA | 0.1 eV |
| ISPIN | 2 |
| MAGMOM | 1 |

> 后续所有 EOS 静态计算须使用相同 ENCUT/KSPACING/POTCAR，不得混用。
