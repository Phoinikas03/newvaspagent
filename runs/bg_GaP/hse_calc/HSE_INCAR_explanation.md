# HSE INCAR 参数说明

## GaP HSE06 带隙计算

### 参数来源

| 参数 | 值 | 来源 |
|------|-----|------|
| ENCUT | 400 eV | 收敛测试确定 |
| KSPACING | 0.15 Å⁻¹ | 收敛测试确定 |
| HFSCREEN | 0.2 | HSE06 标准值 |
| AEXX | 0.25 | HSE06 标准值 |
| ALGO | Damped | 标准半导体推荐 |
| TIME | 0.4 | 配合 ALGO=Damped |
| PRECFOCK | Fast | 加速 HF 积分 |
| KPAR | 8 | 8 GPU 并行 |

### PBE → HSE 参数一致性

以下参数在 PBE 和 HSE 阶段**完全一致**：
- ENCUT = 400 eV
- KSPACING = 0.15 Å⁻¹
- KGAMMA = .TRUE.
- ISMEAR = 0
- SIGMA = 0.05

### HSE 热启动

- `ISTART = 1`：从 PBE 的 WAVECAR 读取初始波函数
- `ICHARG = 2`：从 CHGCAR 读取电荷密度

### 参考文档

- HSE 参数：`bandgap/references/hse_params.md`（标准共价半导体）
- 收敛报告：`convergence_test/Convergence_Report.md`

### 计算日期

2026-04-21
