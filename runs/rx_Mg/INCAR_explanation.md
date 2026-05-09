# Mg 超胞结构优化 INCAR 参数说明

## 材料信息
- **化学式**: Mg (金属)
- **原子数**: 23 个 Mg 原子
- **结构类型**: 超胞

## 参数选择依据

### 电子结构参数
| 参数 | 值 | 说明 |
|------|-----|------|
| `ENCUT` | 520 eV | 取 POTCAR 中最大 ENMAX × 1.3，消除 Pulay 应力 |
| `EDIFF` | 1E-6 | 电子步收敛标准，结构松弛时足够 |
| `PREC` | Accurate | 标准精度，避免基组截断误差 |
| `ALGO` | Normal | 常规迭代算法，稳定可靠 |

### 展宽参数（金属体系）
| 参数 | 值 | 说明 |
|------|-----|------|
| `ISMEAR` | 1 | Methfessel-Paxton 一阶展宽，适用于金属 |
| `SIGMA` | 0.2 | 较大展宽，改善费米面附近 K 点收敛 |

参考：[VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 离子弛豫参数
| 参数 | 值 | 说明 |
|------|-----|------|
| `IBRION` | 2 | 共轭梯度法 (CG)，最稳健 |
| `ISIF` | 3 | 全弛豫：原子位置 + 晶胞形状 + 体积 |
| `NSW` | 200 | 最大离子步数 |
| `EDIFFG` | -0.02 | 力收敛阈值 0.02 eV/Å |
| `POTIM` | 0.5 | CG 步长 |

### K 点设置
| 参数 | 值 | 说明 |
|------|-----|------|
| `KSPACING` | 0.20 | K 点间距 (Å⁻¹) |
| `KGAMMA` | .TRUE. | 包含 Gamma 点 |

## 未做系统收敛说明
**注意**: 本次计算未进行 ENCUT/KSPACING 的系统收敛测试（1 meV/atom 标准）。
- 使用模板默认参数 `ENCUT = 520 eV`, `KSPACING = 0.20 Å⁻¹`
- 若需与文献或后续计算严格可比，建议重新进行收敛测试

## 参考来源
- VASP Wiki: [Volume Relaxation](https://vasp.at/wiki/Volume_relaxation)
- VASP Wiki: [IBRION](https://vasp.at/wiki/IBRION)
- 本地参考: `references/incar_params.md`
