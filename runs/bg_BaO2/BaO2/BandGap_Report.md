# BaO₂ 能带计算报告

## 计算概述

本报告记录 BaO₂（过氧化钡）的 HSE06 杂化泛函能带计算结果。

## 体系信息

- **材料**: BaO₂ (过氧化钡)
- **结构**: 1 Ba + 2 O，共 3 原子单胞
- **POSCAR 来源**: `/mnt/data_x3/xiazeyu/newvaspagent/data/bandgap/BaO2`（已优化结构）

## 计算参数

### 收敛测试结果

| 参数 | 推荐值 |
|------|--------|
| ENCUT | 550 eV |
| KSPACING | 0.15 Å⁻¹ |
| KGAMMA | .TRUE. |

详见：`BaO2/convergence_test/Convergence_Report.md`

### HSE06 参数

| 参数 | 值 |
|------|-----|
| LHFCALC | .TRUE. |
| HFSCREEN | 0.2 Å⁻¹ |
| AEXX | 0.25 |
| ALGO | Damped |
| TIME | 0.4 |
| PRECFOCK | Fast |

## 计算结果

### HSE06 带隙

| 属性 | 值 |
|------|-----|
| **带隙** | **3.82 eV** |
| **带隙类型** | **间接带隙** |
| **跃迁路径** | (0.077, 0.000, 0.462) → (0.000, 0.000, 0.462) |

### 能量收敛

HSE 计算在 13 个电子步后收敛：
- 最终能量: -21.528380 eV
- 能量变化: -8.44 × 10⁻⁶ eV（满足 EDIFF = 1E-5）

## 文件位置

| 文件 | 路径 |
|------|------|
| POSCAR | `BaO2/POSCAR` |
| INCAR (PBE) | `BaO2/pbe_scf/INCAR_pbe` |
| INCAR (HSE) | `BaO2/hse/INCAR_hse` |
| POTCAR | `BaO2/hse/POTCAR` (Ba_sv, O) |
| vasprun.xml | `BaO2/hse/vasprun.xml` |
| OUTCAR | `BaO2/hse/OUTCAR` |
| 收敛报告 | `BaO2/convergence_test/Convergence_Report.md` |
| HSE 参数说明 | `BaO2/hse/HSE_INCAR_explanation.md` |

## 计算日期

2026-04-19

## 备注

- 计算使用 8 × NVIDIA RTX 3090 GPU 并行
- 采用 PBE → HSE 两步法策略
- PBE 预计算提供初始波函数和电荷密度
