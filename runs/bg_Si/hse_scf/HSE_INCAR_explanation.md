# Si HSE06 计算参数说明

## 参数来源

- **ENCUT**: 450 eV — 来自收敛测试（满足≤1 meV/atom判据）
- **KSPACING**: 0.15 Å⁻¹ — 来自收敛测试（满足≤1 meV/atom判据）
- **KGAMMA**: .TRUE. — 与收敛测试一致

## HSE06 参数

根据 `references/hse_params.md` 中"标准共价半导体（Si、Ge、GaAs）"的推荐：

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06标准屏蔽参数 (Å⁻¹) |
| AEXX | 0.25 | HSE06标准精确交换混合比例 |
| ALGO | Damped | 适合大体系，配合TIME参数 |
| TIME | 0.4 | 与ALGO=Damped配合 |
| PRECFOCK | Fast | 加速HF积分 |

## PBE → HSE 参数一致性

| 参数 | PBE | HSE | 说明 |
|------|-----|-----|------|
| ENCUT | 450 eV | 450 eV | 必须一致，WAVECAR兼容 |
| KSPACING | 0.15 | 0.15 | 必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |

## 并行设置

- **GPU数量**: 8张
- **KPAR**: 8（与GPU数对齐）
- **NCORE**: 未设置（GPU场景默认不写）

## 计算流程

1. PBE静态计算 → 生成WAVECAR和CHGCAR
2. HSE计算从PBE结果热启动（ISTART=1, ICHARG=2）
3. 提取带隙信息

## 参考文献

- HSE06标准参数适用于大多数半导体，包括Si
- 参考: J. Chem. Phys. 118, 8207 (2003); J. Chem. Phys. 124, 219906 (2006)
