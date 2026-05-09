# TiC 结构优化 INCAR 参数说明

## 材料信息
- **化学式**: Ti₇C₈ (超胞，15 原子)
- **材料类型**: 过渡金属碳化物，金属性导电

## 关键参数选择依据

### ISMEAR / SIGMA
| 参数 | 值 | 依据 |
|------|-----|------|
| ISMEAR | 1 | TiC 为金属，使用 Methfessel-Paxton 一阶展宽，改善费米面附近的 K 点采样 |
| SIGMA | 0.15 | 适中展宽值，平衡精度与收敛性 |

参考：[VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 离子弛豫参数
| 参数 | 值 | 依据 |
|------|-----|------|
| IBRION | 2 | 共轭梯度法 (CG)，最稳健的优化算法 |
| ISIF | 3 | 全弛豫：原子位置 + 晶胞形状 + 体积 |
| NSW | 200 | 最大离子步数，足够大多数体系收敛 |
| EDIFFG | -0.02 | 力收敛标准 0.02 eV/Å |
| POTIM | 0.5 | CG 步长，默认值 |

### 截断能与 K 点
| 参数 | 值 | 依据 |
|------|-----|------|
| ENCUT | 520 | 模板默认值，取 POTCAR 最大 ENMAX × 1.3 以消除 Pulay 应力 |
| KSPACING | 0.20 | 模板默认值 |
| KGAMMA | .TRUE. | 包含 Γ 点 |

**注意**: 未进行系统的 ENCUT/KSPACING 收敛测试。若后续需要进行高精度能量对比（如 EOS、带隙计算），建议先进行收敛测试。

### 其他参数
| 参数 | 值 | 依据 |
|------|-----|------|
| PREC | Accurate | 标准精度，避免基组截断误差 |
| ALGO | Normal | 常规迭代算法，稳定性好 |
| NCORE | 4 | 并行参数，根据计算节点核数调整 |

## DFT+U 说明
TiC 通常不需要 DFT+U 修正即可进行基本结构优化。若后续电子结构计算显示 d 电子行为异常，可考虑添加 U 值。

## 参考来源
- `references/incar_params.md` (本地)
- [VASP Wiki: 体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)
