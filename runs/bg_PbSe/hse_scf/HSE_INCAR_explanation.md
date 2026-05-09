# PbSe HSE06 计算参数说明

## 计算流程

1. **PBE静态计算** → 生成WAVECAR和CHGCAR
2. **HSE06计算** → 从PBE波函数热启动，计算精确带隙

## 参数一致性

| 参数 | PBE | HSE | 说明 |
|------|-----|-----|------|
| ENCUT | 450 eV | 450 eV | 必须一致，否则WAVECAR无法读取 |
| KSPACING | 0.20 Å⁻¹ | 0.20 Å⁻¹ | 必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |

## HSE06参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06标准屏蔽参数 |
| AEXX | 0.25 | 精确交换混合比例25% |
| ALGO | Damped | 推荐用于大体系 |
| TIME | 0.4 | 与ALGO=Damped配合 |
| PRECFOCK | Fast | 加速HF积分 |

## 并行设置

| 阶段 | GPU数 | KPAR |
|------|-------|------|
| PBE | 2 | 2 |
| HSE | 8 | 8 |

## 参数来源

- HSE06标准参数适用于PbSe等IV-VI族半导体
- 参考：`.claude/skills/bandgap/references/hse_params.md`

## 收敛测试

- ENCUT和KSPACING已通过收敛测试确定
- 收敛报告：`convergence_test/Convergence_Report.md`

---

*文档生成时间: 2026-04-21*
