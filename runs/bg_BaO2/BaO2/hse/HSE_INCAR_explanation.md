# BaO₂ HSE 能带计算参数说明

## 计算流程

采用两步法：
1. **PBE 预计算**：获取 WAVECAR 和 CHGCAR
2. **HSE06 续算**：从 PBE 结果热启动，计算精确带隙

## 参数一致性

PBE 和 HSE 阶段使用完全一致的参数：
- **ENCUT**: 550 eV（收敛测试确定）
- **KSPACING**: 0.15 Å⁻¹（收敛测试确定）
- **KGAMMA**: .TRUE.

## HSE06 参数

BaO₂ 为氧化物，使用标准 HSE06 参数：
- **HFSCREEN**: 0.2 Å⁻¹（HSE06 标准屏蔽参数）
- **AEXX**: 0.25（精确交换混合比例）
- **ALGO**: Damped（配合 TIME=0.4）
- **PRECFOCK**: Fast（加速 HF 积分）

## 收敛测试

详见 `convergence_test/Convergence_Report.md`

## 文件来源

- POSCAR: 已优化结构，来自 `/mnt/data_x3/xiazeyu/newvaspagent/data/bandgap/BaO2`
- POTCAR: Ba_sv, O
- WAVECAR/CHGCAR: 来自 PBE 预计算

## 计算日期

2026-04-19
