# Cr35 结构松弛 INCAR 参数说明

## 材料体系
- **化学式**: Cr35 (35个Cr原子的超胞)
- **材料类型**: 过渡金属，具有磁性（反铁磁性）

---

## 关键参数选择依据

### 电子结构参数
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| `ENCUT` | 520 eV | 根据 POTCAR 中 Cr_pv 的 ENMAX (约 400 eV) × 1.3，遵循 VASP 官方体积松弛指南以消除 Pulay 应力 |
| `EDIFF` | 1E-6 | 电子步收敛标准，结构松弛时足够精确 |
| `PREC` | Accurate | 标准精度，避免基组截断误差 |
| `ALGO` | Normal | 常规迭代算法，对含过渡金属或磁性体系稳定性好 |

### 交换关联
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| `GGA` | PE | PBE 泛函，最常用的 GGA 泛函 |

### 磁性参数
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| `ISPIN` | 2 | Cr 是磁性过渡金属，需自旋极化计算 |
| `MAGMOM` | 35*3.0 | Cr 初始磁矩约 3.0 μB（参考 incar_params.md） |

### 展宽参数
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| `ISMEAR` | 1 | 金属体系使用 Methfessel-Paxton 一阶展宽 |
| `SIGMA` | 0.2 | 较大展宽，改善 K 点收敛 |

参考：[VASP Wiki: Number of k points and method for smearing](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 离子弛豫参数
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| `IBRION` | 2 | 共轭梯度法 (CG)，最稳健，适合初始结构可能较差的体系 |
| `ISIF` | 3 | 同时优化原子位置 + 晶胞形状 + 体积，块体材料标准全弛豫 |
| `NSW` | 200 | 最大离子步数，足够完成收敛 |
| `EDIFFG` | -0.02 | 力收敛标准 0.02 eV/Å |
| `POTIM` | 0.5 | CG 步长 |

### K 点采样
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| `KSPACING` | 0.20 | 使用 INCAR 内置 K 点间距，避免生成 KPOINTS 文件 |
| `KGAMMA` | .TRUE. | 以 Gamma 点为中心的网格 |

---

## 注意事项

1. **POTCAR 选择**: 用户明确要求使用 `Cr_pv` 赝势（包含半核心 p 电子），通过 `setup_vasp_inputs` 的 `potcar_overrides` 参数指定
2. **未进行 ENCUT/KSPACING 收敛测试**: 本次计算使用模板默认参数，未进行系统性的收敛测试
3. **磁性**: Cr 体系可能存在复杂的磁序（如反铁磁），当前设置每个原子初始磁矩 3.0 μB，后续可根据收敛结果调整

---

## 参考来源
- 本地参考文档: `.claude/skills/relax/references/incar_params.md`
- VASP Wiki: [Volume relaxation](https://vasp.at/wiki/Volume_relaxation)
- VASP Wiki: [Number of k points and method for smearing](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
