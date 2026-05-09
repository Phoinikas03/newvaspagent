# Li₁₀Ge(PS₆)₂ 结构优化 INCAR 参数说明

## 材料类型判断

Li₁₀Ge(PS₆)₂ 是一种硫代磷酸盐固态电解质材料，属于：
- **半导体/绝缘体**（硫化物电解质通常带隙在 2-3 eV）
- **无磁性元素**（Li、Ge、P、S 均无磁性）
- **无强关联 d/f 轨道元素**
- **块体材料**

## 关键参数选择依据

### 展宽参数 (ISMEAR / SIGMA)
| 参数 | 值 | 选择依据 |
|------|---|---------|
| ISMEAR | 0 | 半导体/绝缘体使用 Gaussian 展宽，避免人工展宽污染价带顶/导带底附近的真实电子态 |
| SIGMA | 0.05 | 小展宽值，适合半导体体系 |

参考：[VASP Wiki: ISMEAR 选择指南](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 离子弛豫参数
| 参数 | 值 | 选择依据 |
|------|---|---------|
| ISIF | 3 | 块体材料全优化：原子位置 + 晶胞形状 + 体积 |
| IBRION | 2 | 共轭梯度法（CG），最稳健，适合初始结构可能离平衡态较远的体系 |
| NSW | 200 | 最大离子步数，复杂体系（49原子）足够 |
| EDIFFG | -0.02 | 力收敛标准，负值表示力阈值而非能量阈值 |
| POTIM | 0.5 | CG 步长，默认值 |

参考：[VASP Wiki: IBRION 算法说明](https://vasp.at/wiki/IBRION)

### 截断能与 K 点
| 参数 | 值 | 选择依据 |
|------|---|---------|
| ENCUT | 520 eV | 模板默认值，足够覆盖 Li/Ge/P/S 各元素的 ENMAX |
| KSPACING | 0.20 | 模板默认值，适合半导体体系 |
| KGAMMA | .TRUE. | 包含 Gamma 点 |

**注意**：未进行系统 ENCUT/KSPACING 收敛测试。若后续需要进行 EOS、带隙或静态能量对比等高精度计算，建议先进行收敛测试（调用 `convergence` skill）。

### 其他参数
| 参数 | 值 | 选择依据 |
|------|---|---------|
| PREC | Accurate | 标准精度，能有效避免基组截断误差 |
| ALGO | Normal | 常规迭代算法，稳定 |
| EDIFF | 1E-6 | 电子步收敛标准，结构松弛时足够 |
| NCORE | 4 | 并行参数，根据计算节点核数调整 |

## 未使用的参数（不适用于本体系）

- **ISPIN / MAGMOM**：无磁性元素
- **LDAU / LDAUU**：无强关联 d/f 轨道元素
- **IVDW**：无显著的 Van der Waals 弱相互作用
- **LDIPOL / IDIPOL**：非 2D 材料

## 参考来源

1. [VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
2. [VASP Wiki: 体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)
3. [VASP Wiki: 离子松弛算法 (IBRION)](https://vasp.at/wiki/IBRION)
4. 本 skill `references/incar_params.md` 参数参考表