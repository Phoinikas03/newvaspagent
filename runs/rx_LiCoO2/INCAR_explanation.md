# LiCoO2 结构松弛 INCAR 参数说明

## 材料体系
- **化学式**: Li₇Co₈O₁₆ (LiCoO₂ 超胞，31 原子)
- **晶体结构**: 层状氧化物，R-3m 空间群
- **电子结构**: 半导体/绝缘体 (带隙 ~2-3 eV)
- **Co 电子态**: Co³⁺ (d⁶), 低自旋态 (t₂g⁶e_g⁰)

---

## 关键参数选择依据

### 1. 交换关联与 DFT+U

| 参数 | 设置值 | 说明 |
|------|--------|------|
| GGA | PE | PBE 泛函，标准 GGA 近似 |
| LDAU | .TRUE. | 开启 DFT+U 修正 |
| LDAUTYPE | 2 | Dudarev 方法，仅需提供有效 U 值 |
| LDAUL | -1 2 -1 | Li: 无 d 轨道; Co: d 轨道 (l=2); O: 无 d 轨道 |
| LDAUU | 0.0 3.32 0.0 | Co: 3.32 eV (Materials Project 推荐值) |

**参考来源**: [Materials Project Hubbard U Values](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values)

### 2. 自旋极化

| 参数 | 设置值 | 说明 |
|------|--------|------|
| ISPIN | 2 | 开启自旋极化计算 |
| MAGMOM | 7×0.0 8×0.5 16×0.0 | Li: 非磁性; Co: 低自旋 Co³⁺, 初始磁矩 0.5 μB; O: 非磁性 |

**说明**: Co³⁺ 在 LiCoO₂ 中为低自旋态 (S=0)，但开启自旋极化有助于数值稳定性，初始磁矩设小值避免收敛问题。

### 3. 展宽方法

| 参数 | 设置值 | 说明 |
|------|--------|------|
| ISMEAR | 0 | Gaussian 展宽，适用于半导体/绝缘体 |
| SIGMA | 0.05 | 小展宽，避免人工展宽污染价带顶/导带底 |

**参考来源**: [VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 4. 离子弛豫

| 参数 | 设置值 | 说明 |
|------|--------|------|
| IBRION | 2 | 共轭梯度法 (CG)，最稳健 |
| ISIF | 3 | 全松弛：原子位置 + 晶胞形状 + 体积 |
| NSW | 200 | 最大离子步数 |
| EDIFFG | -0.02 | 力收敛标准 (eV/Å) |
| POTIM | 0.5 | CG 步长 |

### 5. 截断能与 K 点

| 参数 | 设置值 | 说明 |
|------|--------|------|
| ENCUT | 520 eV | POTCAR 中最大 ENMAX × 1.3，消除 Pulay 应力 |
| KSPACING | 0.20 Å⁻¹ | K 点网格间距 |
| KGAMMA | .TRUE. | 包含 Γ 点 |

**注意**: 未进行系统性的 ENCUT/KSPACING 收敛测试。若后续需要高精度能量对比（如 EOS、带隙计算），建议先进行收敛测试。

---

## 收敛标准

- **电子步**: EDIFF = 1E-6 eV
- **离子步**: EDIFFG = -0.02 eV/Å (最大原子力 < 0.02 eV/Å)

---

## 文件生成时间
- 日期: 2026-04-25
- 生成方式: relax skill 自动化工作流
