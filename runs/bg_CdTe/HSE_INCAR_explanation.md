# CdTe HSE06 计算参数说明

## PBE → HSE 参数一致性

| 参数 | PBE值 | HSE值 | 说明 |
|------|-------|-------|------|
| ENCUT | 500 eV | 500 eV | 必须一致，否则WAVECAR无法读取 |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | 必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |
| ISMEAR | 0 | 0 | Gaussian展宽 |
| SIGMA | 0.05 | 0.05 | 展宽宽度 |

## HSE06 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 Å⁻¹ | HSE06标准屏蔽参数 |
| AEXX | 0.25 | 精确交换混合比例（HSE06标准值） |
| ALGO | All | 小体系推荐，更稳定 |
| PRECFOCK | Fast | 加速HF积分计算 |

## 并行参数

| 阶段 | GPU数 | KPAR |
|------|-------|------|
| PBE | 2 | 2 |
| HSE | 8 | 8 |

## 参数来源

- HSE06标准参数适用于大多数共价半导体（如CdTe）
- 参考: `.claude/skills/bandgap/references/hse_params.md`

## 收敛测试

ENCUT和KSPACING已通过收敛测试确定（见 `convergence_test/Convergence_Report.md`）：
- 收敛判据: |ΔE| ≤ 1 meV/atom
- ENCUT = 500 eV
- KSPACING = 0.15 Å⁻¹
