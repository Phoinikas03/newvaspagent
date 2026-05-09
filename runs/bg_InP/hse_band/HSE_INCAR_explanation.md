# InP HSE06 计算参数说明

## PBE → HSE 参数一致性

| 参数 | PBE | HSE | 说明 |
|------|-----|-----|------|
| ENCUT | 400 eV | 400 eV | 必须一致，否则 WAVECAR 无法读取 |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | 必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |
| ISMEAR | 0 | 0 | Gaussian 展宽 |
| SIGMA | 0.05 | 0.05 | 展宽参数 |

## HSE06 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06 标准屏蔽参数 (Å⁻¹) |
| AEXX | 0.25 | 精确交换混合比例 |
| ALGO | Damped | 推荐用于大体系 |
| TIME | 0.4 | 与 ALGO=Damped 配合 |
| PRECFOCK | Fast | 加速 HF 积分 |

## 并行参数

| 阶段 | GPU 数 | KPAR | NCORE |
|------|--------|------|-------|
| PBE | 2 | 2 | 不写 |
| HSE | 8 | 8 | 不写 |

## 参数来源

- ENCUT/KSPACING：来自收敛测试（`Convergence_Report.md`）
- HSE 参数：标准 HSE06 参数，参考 `bandgap/references/hse_params.md`
- InP 属于标准 III-V 半导体，使用 HSE06 默认参数即可

## 热启动说明

- `ISTART = 1`：从 PBE 的 WAVECAR 读取初始波函数
- `ICHARG = 2`：从 CHGCAR 读取电荷密度
- 这大幅加速 HSE 收敛，避免从原子轨道开始

---

*生成时间: 2026-04-21*
