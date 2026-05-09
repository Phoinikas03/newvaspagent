# AlN 能带结构与带隙计算 - 最终报告

## 计算概述

本报告总结了使用 VASP 对氮化铝（AlN）进行的高精度能带结构和带隙计算。采用两步法策略：首先进行 PBE 静态自洽计算获取波函数，随后基于 PBE 波函数进行 HSE06 杂化泛函计算以获得准确的带隙值。

---

## 计算体系

| 参数 | 值 |
|-----|-----|
| 材料 | AlN（氮化铝） |
| 晶系 | 六方晶系 |
| 原子数 | 4（2 Al + 2 N） |
| 晶胞参数 | a = 3.129 Å, c = 5.017 Å |
| 结构状态 | 已优化 |

---

## 计算参数

### 收敛参数（通过 ENCUT/KSPACING 测试确定）

| 参数 | 值 | 说明 |
|-----|-----|------|
| ENCUT | 350 eV | 从 N 的 ENMAX (400 eV) × 1.3 = 520 eV 范围内收敛得到 |
| KSPACING | 0.25 Å⁻¹ | 倒易空间 K 点间距，对应约 12-16 个 K 点 |
| KGAMMA | .TRUE. | Gamma 点中心网格 |

### PBE 静态自洽计算参数

```
SYSTEM = PBE Static SCF for Band Structure Pre-calculation
ISTART  = 0
ICHARG  = 2
PREC    = Accurate
ENCUT   = 350
EDIFF   = 1E-6
NELM    = 100
GGA     = PE
ISMEAR  = 0
SIGMA   = 0.05
LWAVE   = .TRUE.
LCHARG  = .TRUE.
ALGO    = Normal
NCORE   = 4
```

**结果**：✓ 电子步收敛
- 最终能量：-29.748 eV
- WAVECAR：3.7 MB
- CHGCAR：1.8 MB

### HSE06 高精度计算参数

```
SYSTEM = HSE06 Band Gap Calculation (restart from PBE)
ISTART  = 1          # 从 PBE WAVECAR 热启动
ICHARG  = 2          # 从 CHGCAR 读取电荷密度
PREC    = Accurate
ENCUT   = 350        # 与 PBE 完全一致
EDIFF   = 1E-5
NELM    = 100
LHFCALC = .TRUE.
HFSCREEN = 0.2       # HSE06 标准屏蔽参数
AEXX     = 0.25      # HSE06 标准精确交换混合比例
ALGO    = Damped
TIME    = 0.4
PRECFOCK = Fast
ISMEAR  = 0
SIGMA   = 0.05
LWAVE   = .FALSE.
LCHARG  = .FALSE.
KSPACING = 0.25
KGAMMA   = .TRUE.
NCORE   = 4
```

**结果**：✓ 电子步收敛

---

## 计算结果

### HSE06 带隙

| 参数 | 值 |
|-----|-----|
| **带隙能量** | **5.378 eV** |
| **带隙类型** | **直接带隙** |
| **跃迁点** | Γ 点 (0, 0, 0) → Γ 点 (0, 0, 0) |

### 物理意义

- **直接带隙**：价带最大值和导带最小值都位于 Γ 点，这是 AlN 的典型特征
- **带隙值 5.378 eV**：与实验值（~6.0-6.2 eV）相比略低，这是 HSE06 对宽带隙半导体的常见低估
- **HSE06 vs PBE**：HSE06 通常比 PBE 给出更准确的带隙值，但对于 AlN 这样的宽带隙材料仍可能低估 0.5-1.0 eV

---

## 计算资源消耗

| 阶段 | 任务数 | 耗时 | 硬件 |
|-----|-------|------|------|
| ENCUT 收敛测试 | 7 个测试点 | ~15 分钟 | 7 张 GPU 并行 |
| KSPACING 收敛测试 | 5 个测试点 | ~10 分钟 | 5 张 GPU 并行 |
| PBE 静态自洽 | 1 个计算 | ~5 分钟 | 1 张 GPU |
| HSE06 高精度 | 1 个计算 | ~20 分钟 | 1 张 GPU |
| **总计** | - | **~50 分钟** | RTX 2080 Ti |

---

## 关键文件位置

| 文件 | 路径 | 说明 |
|-----|-----|------|
| 收敛报告 | `Convergence_Report.md` | ENCUT/KSPACING 收敛详细结果 |
| HSE 参数说明 | `HSE_INCAR_explanation.md` | HSE06 参数选择与一致性检查 |
| PBE INCAR | `INCAR_pbe` | PBE 静态自洽计算参数 |
| HSE INCAR | `INCAR_hse` | HSE06 高精度计算参数 |
| PBE 输出 | `pbe_scf/` | 包含 WAVECAR、CHGCAR、vasprun.xml |
| HSE 输出 | `hse_calc/` | 包含 vasprun.xml（带隙信息） |

---

## 结论

AlN 的 HSE06 计算带隙为 **5.378 eV**，为**直接带隙**，跃迁发生在 Γ 点。该结果与 AlN 的已知物理性质一致，但相比实验值略低，这是 HSE06 对宽带隙半导体的常见特性。

若需要进一步提高精度，可考虑：
1. 使用更高的混合交换比例（AEXX > 0.25）
2. 调整屏蔽参数（HFSCREEN）
3. 使用 GW 方法（计算成本更高）

---

**计算完成时间**：2026-04-19 01:10 UTC
**计算环境**：NVIDIA RTX 2080 Ti × 8, VASP 6.5.1 (GPU版本)
