# HSE06 INCAR 参数说明

## 参数来源

本计算采用标准HSE06杂化泛函参数，适用于GaN等标准共价半导体。

### HSE06核心参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06标准屏蔽参数 (Å⁻¹) |
| AEXX | 0.25 | 精确交换混合比例，HSE06标准值 |
| ALGO | Damped | 适用于标准半导体，配合TIME=0.4 |
| PRECFOCK | Fast | 加速HF积分，精度影响<0.05 eV |

### 与PBE的一致性

以下参数与PBE SCF阶段完全一致：

| 参数 | 值 |
|------|-----|
| ENCUT | 520 eV |
| KSPACING | 0.15 Å⁻¹ |
| KGAMMA | .TRUE. |
| ISMEAR | 0 |
| SIGMA | 0.05 |

### 热启动设置

| 参数 | 值 | 说明 |
|------|-----|------|
| ISTART | 1 | 从PBE WAVECAR读取初始波函数 |
| ICHARG | 2 | 从PBE CHGCAR读取电荷密度 |

### 并行参数

| 参数 | 值 | 说明 |
|------|-----|------|
| KPAR | 8 | 8张GPU，k点并行 |

---

## 参考文献

- J. Heyd, G. E. Scuseria, M. Ernzerhof, J. Chem. Phys. **118**, 8207 (2003)
- J. Heyd et al., J. Chem. Phys. **124**, 219906 (2006)

---
*生成时间: 2026-04-21*
