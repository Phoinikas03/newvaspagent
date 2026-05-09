# SnO2 HSE06 计算参数说明

## PBE → HSE 参数一致性

| 参数 | PBE 值 | HSE 值 | 说明 |
|------|--------|--------|------|
| ENCUT | 550 eV | 550 eV | 必须一致，否则 WAVECAR 无法读取 |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | 必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |

## HSE06 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06 标准屏蔽参数 |
| AEXX | 0.25 | 精确交换混合比例 25% |
| ALGO | Damped | 大体系推荐算法 |
| TIME | 0.4 | 与 Damped 配合 |
| PRECFOCK | Fast | 加速 HF 积分 |

## 并行设置

| 阶段 | GPU 数 | KPAR |
|------|--------|------|
| PBE | 2 | 2 |
| HSE | 8 | 8 |

## 参数来源

- HSE 参数参考：`bandgap/references/hse_params.md`（标准 HSE06 参数）
- SnO2 为氧化物宽带隙半导体，采用标准 HSE06 参数

## 收敛状态

- ENCUT/KSPACING 已通过收敛测试（见 `convergence_test/Convergence_Report.md`）
- 收敛标准：ΔE ≤ 1 meV/atom
