# LiMn₂O₄ 结构松弛 INCAR 参数说明

## 材料特性
LiMn₂O₄ 是尖晶石结构的锂锰氧化物，具有以下特性：
- **强关联体系**：含 Mn 过渡金属，d 轨道电子强关联
- **磁性材料**：Mn³⁺/Mn⁴⁺ 混合价态，具有磁性
- **半导体/绝缘体**：带隙材料

## 关键参数选择依据

### 1. DFT+U 参数
| 参数 | 值 | 说明 |
|------|-----|------|
| LDAU | .TRUE. | 启用 DFT+U |
| LDAUTYPE | 2 | Dudarev 方法（仅需 Ueff = U - J） |
| LDAUL | -1 2 -1 | Li 无需 U，Mn d 轨道 (l=2)，O 无需 U |
| LDAUU | 0.0 3.9 0.0 | Mn Ueff = 3.9 eV (Materials Project 推荐值) |

**参考来源**：[Materials Project Hubbard U Values](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values)

### 2. 磁性设置
| 参数 | 值 | 说明 |
|------|-----|------|
| ISPIN | 2 | 自旋极化计算 |
| MAGMOM | 5*0.0 12*5.0 24*0.0 | 5 Li (非磁), 12 Mn (初始磁矩 5.0 μB), 24 O (非磁) |

Mn 初始磁矩 5.0 μB 对应高自旋 d⁴ 或 d⁵ 构型，是 Mn³⁺/Mn⁴⁰ 的典型值。

### 3. 展宽参数
| 参数 | 值 | 说明 |
|------|-----|------|
| ISMEAR | 0 | Gaussian 展宽（半导体/绝缘体） |
| SIGMA | 0.05 | 小展宽避免污染带边 |

### 4. 离子弛豫参数
| 参数 | 值 | 说明 |
|------|-----|------|
| IBRION | 2 | 共轭梯度法（最稳健） |
| ISIF | 3 | 全弛豫（原子 + 晶胞形状 + 体积） |
| NSW | 200 | 最大离子步数 |
| EDIFFG | -0.02 | 力收敛标准 0.02 eV/Å |
| POTIM | 0.5 | CG 步长 |

### 5. 截断能与 K 点
| 参数 | 值 | 说明 |
|------|-----|------|
| ENCUT | 520 eV | Mn ENMAX ≈ 400 eV，取 1.3 倍消除 Pulay 应力 |
| KSPACING | 0.20 Å⁻¹ | 自动 K 点网格 |
| KGAMMA | .TRUE. | 包含 Γ 点 |

## 备注
- **未进行系统 ENCUT/KSPACING 收敛测试**：本计算使用经验参数，若需与文献严格可比或后续进行 EOS/带隙计算，建议先运行 convergence skill
- **NCORE = 4**：默认并行设置，实际运行时需根据计算节点核数调整
