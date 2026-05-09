# HSE 计算参数说明

## 计算流程

本计算采用两步法：
1. **PBE 预计算**：获取高质量的 WAVECAR 和 CHGCAR
2. **HSE 续算**：基于 PBE 波函数热启动，计算精确带隙

## 参数一致性

以下参数在 PBE 和 HSE 阶段保持一致：
- **ENCUT = 400 eV**（收敛测试推荐值）
- **KSPACING = 0.15 Å⁻¹**（收敛测试推荐值）
- **KGAMMA = .TRUE.**

## HSE06 参数

采用标准 HSE06 参数（适用于 III-V 族半导体）：
- **LHFCALC = .TRUE.**：启用杂化泛函
- **HFSCREEN = 0.2**：屏蔽参数 (Å⁻¹)
- **AEXX = 0.25**：精确交换混合比例
- **ALGO = Damped**：阻尼算法，适合中等体系
- **TIME = 0.4**：阻尼参数
- **PRECFOCK = Fast**：加速 HF 积分

## 并行设置

- **PBE 阶段**：2 GPU，KPAR = 2
- **HSE 阶段**：8 GPU，KPAR = 8

## 热启动

HSE 阶段从 PBE 结果热启动：
- **ISTART = 1**：读取 WAVECAR
- **ICHARG = 2**：读取 CHGCAR

## 参考来源

- HSE 参数参考：`.claude/skills/bandgap/references/hse_params.md`
- 收敛测试报告：`convergence_test/Convergence_Report.md`

---
*生成时间：2026-04-21*
