# Convergence Report — FCC Pt

**POSCAR 来源**：Materials Project mp-126（FCC Pt 原始胞，1 原子，空间群 Fm-3m）
**POTCAR**：Pt（标准赝势，ENMAX=230.283 eV）
**ISMEAR / SIGMA**：1 / 0.2（金属 Methfessel-Paxton）
**PREC**：Accurate，NSW=0，EDIFF=1E-6

---

## ENCUT 收敛（固定 KSPACING=0.15）

| ENCUT (eV) | E_total (eV) | ΔE (meV/atom) |
|---|---|---|
| 250 | -6.10156443 | — |
| 300 | -6.09864194 | 2.92 |
| 350 | -6.09363788 | 5.00 |
| 400 | -6.09428906 | **0.65 ✓** |
| 450 | -6.09451199 | 0.22 |
| 500 | -6.09456099 | 0.05 |

**推荐 ENCUT = 400 eV**（|ΔE(350→400)| = 0.65 meV/atom < 1 meV/atom）

---

## KSPACING 收敛（固定 ENCUT=400 eV）

| KSPACING (Å⁻¹) | E_total (eV) | ΔE (meV/atom) |
|---|---|---|
| 0.30 | -6.07549613 | — |
| 0.25 | -6.09689365 | 21.40 |
| 0.20 | -6.09971752 | 2.82 |
| 0.15 | -6.09428906 | 5.43 |
| 0.10 | -6.09317443 | 1.11 |
| 0.08 | -6.09343952 | **0.27 ✓** |

注：金属 Fermi 面采样导致能量在 0.20/0.15 间出现振荡（典型现象）。
**推荐 KSPACING = 0.10 Å⁻¹**（|ΔE(0.10→0.08)| = 0.27 meV/atom < 1 meV/atom，精度与成本折中）

---

## 最终推荐参数

| 参数 | 值 |
|---|---|
| ENCUT | 400 eV |
| KSPACING | 0.10 Å⁻¹ |
| KGAMMA | .TRUE. |
| ISMEAR | 1 |
| SIGMA | 0.2 |

后续所有 EOS 静态计算须使用相同 ENCUT/KSPACING/POTCAR，且工作目录中不得存在 KPOINTS 文件。
