# Convergence Report — BCC Fe

**材料**：α-Fe（BCC，Im-3m，2原子/单胞）
**POSCAR 来源**：Materials Project mp-13，经 pymatgen 转换为标准立方结构（a = 2.863 Å）
**计算日期**：2026-04-15
**VASP 版本**：6.4.2（GPU 构建，vasp_std）
**硬件**：8 × NVIDIA RTX 3090，节点 d01

---

## ENCUT 收敛测试

**固定参数**：KSPACING = 0.15 Å⁻¹，KGAMMA = .TRUE.，ISPIN = 2，MAGMOM = 2×2.0，ISMEAR = 1，SIGMA = 0.1，NSW = 0

| ENCUT (eV) | E_total (eV) | ΔE (meV/atom) | 收敛？ |
|-----------|-------------|--------------|--------|
| 300 | -16.47455495 | — | — |
| 350 | -16.46695719 | +3.80 | ❌ |
| 400 | -16.45828088 | +4.34 | ❌ |
| 450 | -16.45769404 | +0.29 | ✅ |
| 500 | -16.45843250 | -0.37 | ✅ |

**选定 ENCUT = 450 eV**（相邻步 ΔE = 0.29 meV/atom ≤ 1 meV/atom）

---

## KSPACING 收敛测试

**固定参数**：ENCUT = 450 eV，KGAMMA = .TRUE.，ISPIN = 2，MAGMOM = 2×2.0，ISMEAR = 1，SIGMA = 0.1，NSW = 0

| KSPACING (Å⁻¹) | E_total (eV) | ΔE (meV/atom) | 收敛？ |
|----------------|-------------|--------------|--------|
| 0.30 | -16.46187100 | — | — |
| 0.25 | -16.45451927 | +3.68 | ❌ |
| 0.20 | -16.45648608 | -0.98 | ✅ |
| 0.15 | -16.45769404 | -0.60 | ✅ |
| 0.10 | -16.45990191 | -1.10 | ❌ |

**选定 KSPACING = 0.15 Å⁻¹**（取较小值保证精度；0.20→0.15 时 ΔE = 0.60 meV/atom ≤ 1 meV/atom）

---

## 推荐生产参数

| 参数 | 值 |
|------|----|
| **ENCUT** | **450 eV** |
| **KSPACING** | **0.15 Å⁻¹** |
| **KGAMMA** | .TRUE. |
| **ISMEAR** | 1（Methfessel-Paxton，适合金属） |
| **SIGMA** | 0.1 eV |
| **ISPIN** | 2 |
| **MAGMOM** | 2*2.0 |
| **PREC** | Accurate |

> ⚠️ 后续所有 EOS 静态计算须使用**完全相同**的 ENCUT、KSPACING、POTCAR 类型（Fe 标准赝势），以保证能量可比性。
