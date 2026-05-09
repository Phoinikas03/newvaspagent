# InSe HSE06 计算参数说明

## PBE → HSE 参数一致性

| 参数 | PBE | HSE | 说明 |
|------|-----|-----|------|
| ENCUT | 400 eV | 400 eV | 收敛测试确定，必须一致 |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | 收敛测试确定，必须一致 |
| KGAMMA | .TRUE. | .TRUE. | 必须一致 |

## HSE06 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06 标准屏蔽参数 |
| AEXX | 0.25 | HSE06 标准精确交换混合比例 |
| ALGO | Damped | 推荐用于大体系 |
| TIME | 0.4 | 与 ALGO=Damped 配合 |
| PRECFOCK | Fast | 加速 HF 积分 |

## 并行设置

| 阶段 | GPU 数 | KPAR |
|------|--------|------|
| PBE | 2 | 2 |
| HSE | 8 | 8 |

## 参数来源

- HSE06 标准参数（HFSCREEN=0.2, AEXX=0.25）适用于大多数半导体
- 参考：`.claude/skills/bandgap/references/hse_params.md`

---

*文档生成时间: 2026-04-21*
