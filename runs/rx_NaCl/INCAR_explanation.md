# NaCl 结构松弛 INCAR 参数说明

## 材料类型
NaCl 是典型的离子晶体/绝缘体，带隙约 8.5 eV。

## 关键参数选择

| 参数 | 设置值 | 选择依据 |
|------|--------|----------|
| ISMEAR | 0 | 绝缘体使用 Gaussian 展宽，避免人工展宽污染价带顶/导带底 |
| SIGMA | 0.05 | 小展宽，适合绝缘体 |
| ISIF | 3 | 块体材料全优化（原子位置 + 晶胞形状 + 体积） |
| ENCUT | 520 eV | 取 POTCAR 中最大 ENMAX × 1.3，消除 Pulay 应力 |
| IBRION | 2 | 共轭梯度法（CG），最稳健 |
| NSW | 200 | 最大离子步数 |
| EDIFFG | -0.02 eV/Å | 力收敛标准 |
| KSPACING | 0.20 | 绝缘体可用较稀 K 点网格 |

## 磁性与强关联
- NaCl 非磁性，无需设置 ISPIN/MAGMOM
- Na 和 Cl 无强关联 d/f 电子，无需 DFT+U

## Van der Waals
- 离子键主导，无需 vdW 修正

## 参考来源
- VASP Wiki: [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- VASP Wiki: [体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)

## 备注
- 未进行系统性的 ENCUT/KSPACING 收敛测试，使用模板默认值
- 若需生产级精度，建议先运行 convergence skill 进行收敛测试
