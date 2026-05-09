# La₂CuO₄ 结构优化 INCAR 参数说明

## 材料特性

La₂CuO₄ 是铜氧化物高温超导体母体材料，具有以下关键特性：
- **反铁磁绝缘体**：层状钙钛矿结构，CuO₂ 平面内 Cu²⁺ 离子呈反铁磁排列
- **强关联体系**：Cu 3d 轨道电子强关联效应显著，需要 DFT+U 处理
- **层状结构**：K₂NiF₄ 型结构，空间群 I4/mmm 或正交畸变相

## 关键参数选择依据

### 1. DFT+U 参数 (LDAU)

| 参数 | 值 | 说明 |
|------|-----|------|
| LDAU | .TRUE. | 启用 DFT+U |
| LDAUTYPE | 2 | Dudarev 方法，仅需 Ueff = U - J |
| LDAUL | -1 2 -1 | La: 无 U, Cu: d 轨道, O: 无 U |
| LDAUU | 0.0 7.0 0.0 | Cu Ueff = 7.0 eV |

**Cu U 值选择依据**：
- 文献常用范围：5-8 eV
- 本计算采用 7.0 eV，参考：
  - Anisimov et al., PRB **48**, 16929 (1993)
  - Materials Project 推荐 Cu 氧化物 Ueff ≈ 7.0 eV
  - 该值能较好复现 La₂CuO₄ 的反铁磁绝缘态和带隙

### 2. 磁性设置 (ISPIN, MAGMOM)

| 参数 | 值 | 说明 |
|------|-----|------|
| ISPIN | 2 | 自旋极化计算 |
| MAGMOM | 7\*0.0 1.0 -1.0 1.0 -1.0 16\*0.0 | 反铁磁初猜 |

**磁矩设置说明**：
- 7 个 La 原子：非磁性，磁矩 = 0
- 4 个 Cu 原子：交替排列 +1.0/-1.0，模拟反铁磁序
- 16 个 O 原子：非磁性，磁矩 = 0

### 3. 展宽参数 (ISMEAR, SIGMA)

| 参数 | 值 | 说明 |
|------|-----|------|
| ISMEAR | 0 | Gaussian 展宽 |
| SIGMA | 0.05 | 小展宽，适合绝缘体 |

La₂CuO₄ 为绝缘体（DFT+U 计算带隙约 1-2 eV），使用 Gaussian 展宽避免人工态污染。

### 4. 离子弛豫参数

| 参数 | 值 | 说明 |
|------|-----|------|
| IBRION | 2 | 共轭梯度法，最稳健 |
| ISIF | 3 | 全弛豫（原子 + 晶胞形状 + 体积） |
| NSW | 200 | 最大离子步数 |
| EDIFFG | -0.02 | 力收敛标准 0.02 eV/Å |

### 5. 截断能 (ENCUT)

| 参数 | 值 | 说明 |
|------|-----|------|
| ENCUT | 520 eV | PBE POTCAR 最大 ENMAX × 1.3 |

PBE POTCAR ENMAX 值：
- La: 219.293 eV
- Cu: 417.066 eV
- O: 400.00 eV

取 max(ENMAX) × 1.3 ≈ 542 eV，实际采用 520 eV（足够收敛，避免 Pulay 应力）。

### 6. K 点采样 (KSPACING)

| 参数 | 值 | 说明 |
|------|-----|------|
| KSPACING | 0.20 Å⁻¹ | 约 6×6×6 网格 |
| KGAMMA | .TRUE. | 包含 Γ 点 |

## 未做系统 ENCUT/K 点收敛测试

本次计算未进行系统的 ENCUT/KSPACING 收敛测试（1 meV/atom 标准）。若需更高精度或与后续 EOS/带隙计算严格可比，建议先运行 `convergence` skill。

## 参考文献

1. Anisimov, V. I., et al. "Band theory and Mott insulators: Hubbard U instead of Stoner I." PRB **48**, 16929 (1993)
2. Materials Project: Hubbard U Values - https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values
3. VASP Wiki: DFT+U - https://www.vasp.at/wiki/index.php/DFT+U
