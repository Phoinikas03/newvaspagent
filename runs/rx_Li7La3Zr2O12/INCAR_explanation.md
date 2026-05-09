# Li7La3Zr2O12 (LLZO) 结构优化 INCAR 参数说明

## 材料信息
- **化学式**: Li7La3Zr2O12
- **结构**: 立方相石榴石结构 (Ia-3d)
- **原子数**: 95 (Li:27, La:12, Zr:8, O:48)
- **材料类型**: 固态电解质，宽带隙绝缘体
- **实验带隙**: ~5-6 eV

## POTCAR 选择
| 元素 | POTCAR | ENMAX (eV) | 说明 |
|------|--------|------------|------|
| Li   | Li     | 140.000    | 标准版本 |
| La   | La     | 219.292    | 标准版本 |
| Zr   | Zr_sv  | 229.898    | 无标准版本，使用 sv |
| O    | O      | 400.000    | 标准版本 |

**ENCUT = 520 eV**: 取最大 ENMAX (O: 400) × 1.3，消除 Pulay 应力

## 关键参数选择依据

### ISMEAR = 0, SIGMA = 0.05
- LLZO 为宽带隙绝缘体，使用 Gaussian 展宽
- 参考: [VASP Wiki: ISMEAR 选择规范](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### ISIF = 3
- 块体材料全弛豫：原子位置 + 晶胞形状 + 体积
- 参考: [VASP Wiki: Volume Relaxation](https://vasp.at/wiki/Volume_relaxation)

### IBRION = 2 (CG)
- 共轭梯度法，最稳健
- 适合初始结构可能偏离平衡态的情况

### NSW = 300
- 95 原子体系，需要足够的离子步

### KSPACING = 0.30
- 绝缘体可用较稀 K 点网格
- KGAMMA = .TRUE. 包含 Gamma 点

### 未使用 DFT+U
- La 和 Zr 的 d/f 轨道关联较弱，PBE 计算通常足够
- 如需高精度带隙，可在后续 electronic-structure 计算中考虑 HSE06

## 收敛标准
- EDIFF = 1E-6 (电子步)
- EDIFFG = -0.02 eV/Å (力收敛)

## 备注
- 本次计算未进行 ENCUT/KSPACING 收敛测试
- 如需与文献严格对比，建议先运行 convergence skill