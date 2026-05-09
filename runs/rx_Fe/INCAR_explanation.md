# Fe 结构优化 INCAR 参数说明

## 材料类型
- **Fe (铁)**: 铁磁性金属
- **结构**: 35 原子超胞

## 关键参数选择依据

### 磁性设置
| 参数 | 值 | 说明 |
|------|-----|------|
| `ISPIN` | 2 | 自旋极化计算，Fe 为铁磁性金属 |
| `MAGMOM` | 35*5.0 | 35 个 Fe 原子，每个初始磁矩 5.0 μB |

参考: `references/incar_params.md` 中磁性材料推荐值

### 展宽设置 (金属)
| 参数 | 值 | 说明 |
|------|-----|------|
| `ISMEAR` | 1 | Methfessel-Paxton 一阶展宽，适用于金属 |
| `SIGMA` | 0.2 | 金属用较大展宽，改善 K 点收敛 |

参考: VASP Wiki [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 截断能
| 参数 | 值 | 说明 |
|------|-----|------|
| `ENCUT` | 520 | Fe POTCAR ENMAX ~300 eV，取约 1.7x 以消除 Pulay 应力 |

参考: VASP Wiki [体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)

### K 点
| 参数 | 值 | 说明 |
|------|-----|------|
| `KSPACING` | 0.15 | 金属需要较密 K 点网格 |
| `KGAMMA` | .TRUE. | 包含 Gamma 点 |

### 离子弛豫
| 参数 | 值 | 说明 |
|------|-----|------|
| `IBRION` | 2 | 共轭梯度法 (CG)，最稳健 |
| `ISIF` | 3 | 全弛豫：原子位置 + 晶胞形状 + 体积 |
| `NSW` | 200 | 最大离子步数 |
| `EDIFFG` | -0.02 | 力收敛标准 0.02 eV/Å |
| `POTIM` | 0.5 | CG 步长 |

## 收敛测试说明
**未进行系统 ENCUT/KSPACING 收敛测试**。参数基于经验值和模板默认值。
如需生产级精度，建议在正式计算前运行 `convergence` skill 进行静态单点收敛测试。

## 参考来源
- 本地参考文档: `.claude/skills/relax/references/incar_params.md`
- VASP Wiki: ISMEAR 选择规范
- Materials Project: Fe 磁矩推荐值
