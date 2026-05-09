# HSE06 INCAR 参数说明

## 计算流程

本计算采用"PBE预计算 → HSE续算"的两步法策略：

1. **PBE静态自洽**：获得高质量波函数（WAVECAR）和电荷密度（CHGCAR）
2. **HSE06高精度计算**：基于PBE波函数热启动，获得准确带隙

---

## 参数一致性

以下参数在PBE和HSE两阶段必须完全一致：

| 参数 | 值 | 来源 |
|------|-----|------|
| ENCUT | 520 eV | 收敛测试确定 |
| KSPACING | 0.15 Å⁻¹ | 收敛测试确定 |
| KGAMMA | .TRUE. | 与测试一致 |

---

## HSE06 参数

采用标准HSE06参数（适用于SiC等标准共价半导体）：

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 Å⁻¹ | HSE06标准屏蔽参数 |
| AEXX | 0.25 | 精确交换混合比例 |
| ALGO | Damped | 推荐用于大体系 |
| TIME | 0.4 | 与ALGO=Damped配合 |
| PRECFOCK | Fast | 加速HF积分 |

**参考来源**：`bandgap/references/hse_params.md`

---

## 并行设置

| 阶段 | GPU数 | KPAR | 说明 |
|------|-------|------|------|
| PBE | 2 | 2 | 与GPU数对齐 |
| HSE | 8 | 8 | 与GPU数对齐 |

---

## 热启动参数

| 参数 | 值 | 说明 |
|------|-----|------|
| ISTART | 1 | 从WAVECAR读取初始波函数 |
| ICHARG | 2 | 从CHGCAR读取电荷密度 |

---

## 收敛测试报告

详见：`/home/xiazeyu21/newvaspagent/runs/bg_SiC/convergence_test/Convergence_Report.md`
