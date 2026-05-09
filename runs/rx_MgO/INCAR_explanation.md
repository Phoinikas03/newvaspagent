# MgO 结构优化 INCAR 参数说明

## 材料特性
- **化学式**: Mg₁₁O₁₂（超胞，23 原子）
- **材料类型**: 宽禁带绝缘体（带隙 ~7.7 eV）
- **磁性**: 非磁性
- **DFT+U**: 不需要（Mg²⁺ 和 O²⁻ 电子组态稳定）

## 关键参数选择依据

| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| `ISMEAR` | 0 | MgO 为绝缘体，使用 Gaussian 展宽最安全 |
| `SIGMA` | 0.05 | 小展宽，避免人工展宽污染价带顶/导带底 |
| `ISIF` | 3 | 块体材料全优化：原子位置 + 晶胞形状 + 体积 |
| `IBRION` | 2 | 共轭梯度法（CG），最稳健的松弛算法 |
| `ENCUT` | 520 eV | 取 POTCAR 中最大 ENMAX × 1.3，消除 Pulay 应力 |
| `KSPACING` | 0.20 | 模板默认值，未做系统收敛测试 |
| `KPAR` | 8 | 8 GPU 并行，k 点并行数与 GPU 数对齐 |
| `NCORE` | - | 已删除（GPU 场景不使用 CPU 并行参数） |

## 参考来源
- `references/incar_params.md` - 本地参数参考文档
- VASP Wiki: [Number of k points and method for smearing](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- VASP Wiki: [Volume relaxation](https://vasp.at/wiki/Volume_relaxation)

## 备注
- **未进行 ENCUT/KSPACING 收敛测试**：使用模板默认值
- 若需更高精度或与后续计算（EOS、带隙）严格可比，建议先进行收敛测试
