# INCAR 参数说明文档

## 计算体系
- **材料**: Cr (铬) 金属体系
- **原子数**: 35 个 Cr 原子
- **计算类型**: 全结构松弛 (Full Structural Relaxation)
- **体系特征**: 磁性金属

---

## 关键参数选择依据

### 电子结构参数
| 参数 | 设定值 | 选择依据 |
|------|--------|----------|
| `ENCUT` | 520 eV | 取 POTCAR 中 Cr_pv 的 ENMAX × 1.3，消除体积变化时的 Pulay 应力 |
| `EDIFF` | 1E-6 | 结构松弛标准收敛精度 |
| `PREC` | Accurate | 标准精度，有效避免基组截断误差 |
| `ALGO` | Normal | 常规迭代算法，对磁性体系比 Fast 更稳定 |

### 磁性参数
| 参数 | 设定值 | 选择依据 |
|------|--------|----------|
| `ISPIN` | 2 | 自旋极化计算，Cr 为铁磁性金属 |
| `MAGMOM` | 35\*3.0 | 35 个 Cr 原子，每个初始磁矩 3.0 μB（参考 incar_params.md 中 Cr 的推荐值） |

### 展宽参数（金属体系）
| 参数 | 设定值 | 选择依据 |
|------|--------|----------|
| `ISMEAR` | 1 | Methfessel-Paxton 一阶展宽，改善金属费米面附近 K 点采样 |
| `SIGMA` | 0.2 | 较大展宽，改善 K 点收敛性 |

**注意**: ISMEAR=1 绝不能用于半导体/绝缘体，会导致错误结果。

### 离子弛豫参数
| 参数 | 设定值 | 选择依据 |
|------|--------|----------|
| `IBRION` | 2 | 共轭梯度法 (CG)，最稳健，适合初始结构可能偏离平衡态的情况 |
| `ISIF` | 3 | 全结构优化：原子位置 + 晶胞形状 + 体积 |
| `NSW` | 200 | 最大离子步数，足够复杂体系收敛 |
| `EDIFFG` | -0.02 | 力收敛阈值 0.02 eV/Å，标准精度 |
| `POTIM` | 0.5 | CG 步长，若出现 BRIONS 警告可减小到 0.3 |

### K 点设置
| 参数 | 设定值 | 选择依据 |
|------|--------|----------|
| `KSPACING` | 0.15 | 金属需较密 K 点网格，0.15 Å⁻¹ 确保足够精度 |
| `KGAMMA` | .TRUE. | 包含 Gamma 点 |

---

## 赝势选择
- **POTCAR**: PAW_PBE Cr_pv
- **ZVAL**: 12 个价电子（含半核心态 3p）
- **依据**: Cr 过渡金属推荐使用 semi-core 赝势 Cr_pv，比标准 Cr 赝势更精确

---

## 参考来源
1. VASP Wiki: [Number of k points and method for smearing](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
2. VASP Wiki: [Volume relaxation](https://vasp.at/wiki/Volume_relaxation)
3. relax skill: `references/incar_params.md`

---

## 备注
- 未做系统 ENCUT/K 点收敛测试（用户未要求）
- 如需更高精度静态计算或 EOS 拟合，建议先做 ENCUT/KSPACING 收敛测试
