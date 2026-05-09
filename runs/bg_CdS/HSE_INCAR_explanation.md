# CdS HSE06 能带计算参数说明

## 计算体系
- **材料**: CdS (Cadmium Sulfide)
- **结构**: 纤锌矿 (Wurtzite)
- **晶格常数**: a = 4.17 Å, c = 6.78 Å
- **原子数**: 4 (2 Cd + 2 S)

## 计算参数

### PBE 预计算
| 参数 | 值 | 说明 |
|------|-----|------|
| ENCUT | 520 eV | 截断能 |
| KSPACING | 0.15 Å⁻¹ | K点间距 |
| KGAMMA | .TRUE. | 包含Γ点 |
| ISMEAR | 0 | Gaussian展宽 |
| SIGMA | 0.05 | 展宽宽度 |
| EDIFF | 1E-6 | 电子收敛标准 |
| ALGO | Normal | 算法 |

### HSE06 计算
| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06标准屏蔽参数 |
| AEXX | 0.25 | 精确交换混合比例 |
| ALGO | Damped | 阻尼算法 |
| TIME | 0.4 | 阻尼时间参数 |
| PRECFOCK | Fast | 加速HF积分 |
| ENCUT | 520 eV | 与PBE一致 |
| KSPACING | 0.15 Å⁻¹ | 与PBE一致 |

## 计算资源
- **GPU**: 8 × NVIDIA RTX 3090
- **PBE耗时**: ~45秒
- **HSE耗时**: ~2.5小时

## 收敛状态
- PBE: 14步电子收敛
- HSE: 13步电子收敛

## 参考
- HSE参数来源: 标准HSE06参数，适用于半导体材料
- 参数参考文档: `.claude/skills/bandgap/references/hse_params.md`
