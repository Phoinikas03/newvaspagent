# HSE INCAR 参数说明

## 材料体系
- **材料**: 金刚石碳 (C diamond)
- **结构**: 六方晶胞，2 原子

## PBE → HSE 参数传递

| 参数 | PBE SCF | HSE06 | 说明 |
|------|---------|-------|------|
| ENCUT | 520 eV | 520 eV | 必须一致，否则 WAVECAR 无法读取 |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | 必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |
| ISTART | 0 | 1 | HSE 从 PBE WAVECAR 热启动 |
| ICHARG | 2 | 2 | 从 CHGCAR 读取电荷密度 |

## HSE06 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 Å⁻¹ | HSE06 标准屏蔽参数 |
| AEXX | 0.25 | HSE06 标准精确交换混合比例 |
| ALGO | Damped | 推荐用于大体系 |
| TIME | 0.4 | 与 ALGO=Damped 配合 |
| PRECFOCK | Fast | 加速 HF 积分 |

## 参数来源

- **HSE 参数**: 参考 `references/hse_params.md` 中"标准共价半导体（Si、Ge、GaAs）"条目
- **金刚石碳属于标准共价半导体**，使用 HSE06 默认参数即可

## 收敛测试

- ENCUT 和 KSPACING 通过收敛测试确定
- 详见: `convergence_test/Convergence_Report.md`
