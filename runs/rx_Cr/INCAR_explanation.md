# Cr 结构优化 INCAR 参数说明

## 材料体系
- **化学式**: Cr（铬）
- **原子数**: 35 个原子的超胞
- **材料类型**: 过渡金属（反铁磁）

## 关键参数选择依据

### 1. ISMEAR / SIGMA
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| ISMEAR | 1 | Methfessel-Paxton 一阶展宽，适用于金属体系 |
| SIGMA | 0.2 | 金属体系推荐值，改善费米面附近 K 点收敛 |

**参考**: [VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 2. 磁性设置
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| ISPIN | 2 | 自旋极化计算，Cr 为反铁磁金属 |
| MAGMOM | 35*3.0 | 每个 Cr 原子初始磁矩 3.0 μB（参考 incar_params.md） |

### 3. 离子弛豫
| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| IBRION | 2 | 共轭梯度法（CG），最稳健 |
| ISIF | 3 | 块体材料全优化：原子 + 晶胞形状 + 体积 |
| NSW | 200 | 最大离子步数 |
| EDIFFG | -0.02 | 力收敛标准 0.02 eV/Å |
| POTIM | 0.5 | CG 步长 |

### 4. 截断能与 K 点
| 参数 | 设置值 | 说明 |
|------|--------|------|
| ENCUT | 520 eV | 取 POTCAR 最大 ENMAX × 1.3，消除 Pulay 应力 |
| KSPACING | 0.20 Å⁻¹ | 模板默认值 |
| KGAMMA | .TRUE. | 包含 Gamma 点 |

**注意**: 未进行系统 ENCUT/KSPACING 收敛测试。若需生产级精度或与后续计算（EOS、带隙）严格可比，建议先运行 `convergence` skill。

### 5. 并行参数（GPU 优化）
| 参数 | 设置值 | 说明 |
|------|--------|------|
| KPAR | 8 | k 点并行数 = GPU 数（8 × RTX 2080 Ti）|
| NCORE | 已删除 | GPU 计算不应保留 CPU 并行参数 |

## 参考来源
- 本地参考文档: `references/incar_params.md`
- VASP Wiki: [Volume Relaxation](https://vasp.at/wiki/Volume_relaxation)
- VASP Wiki: [IBRION](https://vasp.at/wiki/IBRION)

## 生成时间
2026-04-24
