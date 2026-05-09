# LiFePO4 结构优化 INCAR 参数说明

## 材料特性分析

| 特性 | 分析结果 | 参数设置 |
|------|---------|---------|
| 电子结构 | 半导体/绝缘体（带隙 ~3.5 eV） | `ISMEAR = 0`, `SIGMA = 0.05` |
| 磁性 | Fe²⁺ 高自旋（d6），反铁磁 | `ISPIN = 2`, `MAGMOM = 4*5.0` |
| 强关联 | Fe 3d 轨道强关联 | `LDAU = .TRUE.`, `LDAUU = 5.3 eV` |
| 结构类型 | 块体材料 | `ISIF = 3`（全优化） |

## 关键参数选择依据

### ISMEAR / SIGMA
- **选择**: `ISMEAR = 0`, `SIGMA = 0.05`
- **依据**: LiFePO4 是宽带隙半导体（~3.5 eV），使用 Gaussian 展宽避免人工展宽污染价带顶/导带底
- **参考**: [VASP Wiki: ISMEAR 选择规范](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 磁性参数 (ISPIN / MAGMOM)
- **选择**: `ISPIN = 2`, `MAGMOM = 3*0 4*5.0 4*0 16*0`
- **依据**: Fe²⁺ 高自旋态（d6, S=2），初始磁矩设为 5.0 μB
- **说明**: 实际磁矩会在自洽计算中收敛到物理值

### DFT+U 参数
- **选择**: `LDAUU = 5.3 eV` (Fe)
- **依据**: Materials Project 数据库对 Fe 氧化物的标准取值
- **参考**: [Materials Project Hubbard U Values](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values)

### ENCUT / KSPACING
- **选择**: `ENCUT = 520 eV`, `KSPACING = 0.20 Å⁻¹`
- **说明**: 使用模板默认值，未进行系统收敛测试
- **备注**: 若需与文献或后续高精度计算严格可比，建议先进行 ENCUT/KSPACING 收敛测试

### ISIF
- **选择**: `ISIF = 3`
- **依据**: 块体材料全优化（原子位置 + 晶胞形状 + 体积）

### IBRION / POTIM
- **选择**: `IBRION = 2`, `POTIM = 0.5`
- **依据**: 共轭梯度法最稳健，适合初始结构可能偏离平衡态的情况

## 参考来源

1. VASP Wiki: [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
2. VASP Wiki: [体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)
3. Materials Project: [GGA+U 计算中 U 值的选取方法与列表](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values)
