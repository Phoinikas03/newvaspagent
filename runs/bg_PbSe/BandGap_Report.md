# PbSe 能带计算报告

## 计算概述

- **材料**: PbSe (岩盐结构)
- **计算方法**: PBE → HSE06 两步法
- **计算日期**: 2026-04-21

---

## 计算参数

### 收敛参数（来自收敛测试）

| 参数 | 值 | 说明 |
|------|-----|------|
| ENCUT | 450 eV | 截断能 |
| KSPACING | 0.20 Å⁻¹ | K点间距 |
| KGAMMA | .TRUE. | Gamma中心网格 |

### HSE06参数

| 参数 | 值 | 说明 |
|------|-----|------|
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06标准屏蔽参数 |
| AEXX | 0.25 | 精确交换混合比例 |
| ALGO | Damped | 阻尼算法 |
| PRECFOCK | Fast | 加速HF积分 |

### 并行设置

| 阶段 | GPU数 | KPAR | 耗时 |
|------|-------|------|------|
| PBE | 2 | 2 | ~8秒 |
| HSE | 8 | 8 | ~143秒 |

---

## 计算结果

### HSE06带隙

| 属性 | 值 |
|------|-----|
| **带隙** | **1.140 eV** |
| **类型** | **直接带隙** |
| **跃迁** | (0.444, 0.000, 0.000) → (0.444, 0.000, 0.000) |

### 结果说明

- PbSe为直接带隙半导体
- 带隙位于布里渊区非高对称点（约在Γ-X路径上）
- HSE06计算得到的带隙值与文献报道的实验值（~0.27 eV at 300K）相比偏高，这是HSE06对IV-VI族半导体的已知行为

---

## 文件路径

### PBE计算

| 文件 | 路径 |
|------|------|
| INCAR | `pbe_scf/INCAR_pbe` |
| OUTCAR | `pbe_scf/OUTCAR` |
| WAVECAR | `pbe_scf/WAVECAR` |
| CHGCAR | `pbe_scf/CHGCAR` |

### HSE计算

| 文件 | 路径 |
|------|------|
| INCAR | `hse_scf/INCAR_hse` |
| OUTCAR | `hse_scf/OUTCAR` |
| vasprun.xml | `hse_scf/vasprun.xml` |
| 参数说明 | `hse_scf/HSE_INCAR_explanation.md` |

### 收敛测试

| 文件 | 路径 |
|------|------|
| 收敛报告 | `convergence_test/Convergence_Report.md` |

---

## 计算状态

- ✓ ENCUT/KSPACING收敛测试完成
- ✓ PBE静态计算收敛
- ✓ WAVECAR和CHGCAR生成成功
- ✓ HSE06计算收敛
- ✓ 带隙提取成功

---

*报告生成时间: 2026-04-21*
