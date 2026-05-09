# HSE06 计算参数说明

## 参数来源

- **HFSCREEN = 0.2**: HSE06标准屏蔽参数
- **AEXX = 0.25**: HSE06标准精确交换混合比例
- **ALGO = Damped**: 适合GaAs等标准共价半导体
- **TIME = 0.4**: 与ALGO=Damped配合

以上参数参考自 `references/hse_params.md` 中"标准共价半导体（Si、Ge、GaAs）"的推荐值。

## PBE → HSE 参数一致性

| 参数 | PBE值 | HSE值 | 说明 |
|------|-------|-------|------|
| ENCUT | 400 eV | 400 eV | 必须一致，确保WAVECAR可读 |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | 必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |

## 热启动设置

- **ISTART = 1**: 从PBE的WAVECAR读取初始波函数
- **ICHARG = 2**: 从CHGCAR读取电荷密度

## 计算成本说明

HSE06杂化泛函计算成本远高于PBE，预计需要数小时完成。
