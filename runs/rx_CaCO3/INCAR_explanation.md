# CaCO3 结构松弛 INCAR 参数说明

## 材料体系分析

- **化学式**: Ca₇C₈O₂₄（方解石超胞，39 原子）
- **电子结构**: 绝缘体（带隙约 3-4 eV）
- **磁性**: 无磁性元素，无需 ISPIN/MAGMOM
- **强关联**: 无 d/f 轨道，无需 DFT+U
- **vdW 相互作用**: 离子晶体，无显著 vdW，无需 IVDW

## 关键参数选择依据

| 参数 | 设置值 | 选择理由 |
|------|--------|----------|
| `ISMEAR` | 0 | 绝缘体使用 Gaussian 展宽，避免人工展宽污染价带顶/导带底 |
| `SIGMA` | 0.05 | 小展宽，适合绝缘体 |
| `ISIF` | 3 | 块体材料全松弛（原子位置 + 晶胞形状 + 体积） |
| `ENCUT` | 520 eV | Ca POTCAR ENMAX ≈ 358 eV, C/O ≈ 400 eV；取最大 × 1.3 ≈ 520 eV |
| `EDIFFG` | -0.02 | 力收敛标准 0.02 eV/Å，适合一般结构优化 |
| `IBRION` | 2 | 共轭梯度法，最稳健 |
| `KSPACING` | 0.20 | 绝缘体，0.20 Å⁻¹ 的 K 点密度已足够 |
| `KGAMMA` | .TRUE. | 包含 Γ 点，适合绝缘体 |

## ENCUT/KSPACING 收敛说明

**本次计算未进行系统性的 ENCUT/KSPACING 收敛测试**。

- 使用模板默认值 ENCUT = 520 eV、KSPACING = 0.20 Å⁻¹
- 若需与文献或后续 EOS/带隙计算严格可比，建议先执行 `convergence` skill 的静态单点收敛测试（目标 1 meV/atom）

## 参考来源

- VASP Wiki: [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- VASP Wiki: [体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)
- 本 skill `references/incar_params.md`