# SiO2 结构松弛 INCAR 参数说明

## 材料类型
- **化学式**: Si7O16
- **分类**: 绝缘体/宽禁带半导体
- **磁性**: 非磁性
- **强关联**: 无（Si 和 O 为主族元素）

## 参数选择依据

### 展宽参数 (ISMEAR / SIGMA)
| 参数 | 值 | 依据 |
|------|-----|------|
| ISMEAR | 0 | SiO2 为绝缘体，使用 Gaussian 展宽最安全 |
| SIGMA | 0.05 | 小展宽避免人工展宽污染价带顶/导带底 |

**参考**: `references/incar_params.md` - 半导体/绝缘体部分

### 离子弛豫参数
| 参数 | 值 | 依据 |
|------|-----|------|
| IBRION | 2 | 共轭梯度法 CG，最稳健的优化算法 |
| ISIF | 3 | 块体材料全弛豫（原子+晶胞形状+体积）|
| NSW | 200 | 最大离子步数，足够收敛 |
| EDIFFG | -0.02 | 力收敛标准 0.02 eV/Å |
| POTIM | 0.5 | CG 步长 |

**参考**: `references/incar_params.md` - ISIF 选择指南

### 电子结构参数
| 参数 | 值 | 依据 |
|------|-----|------|
| ENCUT | 520 eV | POTCAR 中最大 ENMAX × 1.3，消除 Pulay 应力 |
| EDIFF | 1E-6 | 电子步收敛标准 |
| PREC | Accurate | 标准精度，避免基组截断误差 |
| ALGO | Normal | 常规迭代算法，稳定 |

### K 点采样
| 参数 | 值 | 依据 |
|------|-----|------|
| KSPACING | 0.20 | 绝缘体标准 K 点间距 |
| KGAMMA | .TRUE. | 包含 Γ 点 |

### 未使用的参数
- **ISPIN / MAGMOM**: 非磁性体系，无需设置
- **LDAU / LDAUU**: 无 d/f 轨道强关联，无需 DFT+U
- **IVDW**: 共价网络结构，无需 vdW 修正

## 收敛测试说明
**未进行系统 ENCUT/KSPACING 收敛测试**。使用模板默认参数。
若需生产级精度参数，建议后续运行 `convergence` skill 进行静态单点收敛测试。

## 参考来源
- `references/incar_params.md`
- VASP Wiki: [Number of k points and method for smearing](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- VASP Wiki: [Volume relaxation](https://vasp.at/wiki/Volume_relaxation)
