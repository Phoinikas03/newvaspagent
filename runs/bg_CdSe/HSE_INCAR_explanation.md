# HSE06 计算参数说明

## 材料体系
- **化学式**: CdSe
- **结构**: 六方纤锌矿 (Wurtzite)
- **原子数**: 4 (2 Cd + 2 Se)

## 计算流程

### PBE 预计算 (已完成)
- **目的**: 为 HSE 提供初始波函数和电荷密度
- **参数**:
  - ENCUT = 520 eV
  - KSPACING = 0.20
  - ISMEAR = 0, SIGMA = 0.05
- **状态**: ✅ 已收敛，WAVECAR 和 CHGCAR 已生成

### HSE06 计算 (待执行)
- **目的**: 获得准确的带隙值
- **参数来源**: 标准HSE06参数，适用于II-VI族半导体

## HSE 参数设置

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06 标准屏蔽参数 (Å⁻¹) |
| AEXX | 0.25 | 精确交换混合比例 |
| ALGO | Damped | 推荐用于中等体系 |
| TIME | 0.4 | 与 Damped 算法配合 |
| PRECFOCK | Fast | 加速 HF 积分 |

## 一致性保证
- **ENCUT**: PBE 与 HSE 完全一致 (520 eV)
- **KSPACING**: PBE 与 HSE 完全一致 (0.20)
- **KGAMMA**: PBE 与 HSE 完全一致 (.TRUE.)

## 并行设置
- **KPAR = 4**: 对应 4 张 GPU
- HSE 计算中 k 点并行效率高

## 参考来源
- HSE 参数: `references/hse_params.md` - 标准共价半导体
- CdSe 属于 II-VI 族半导体，适用标准 HSE06 参数

## 备注
- 未进行系统性的 ENCUT/KSPACING 收敛测试（用户选择使用模板参数）
- POTCAR 使用标准版本 (Cd, Se)
