# BN HSE06能带结构计算报告

## 计算体系
- **材料**: BN (六方晶系，类石墨结构)
- **原子数**: 4 atoms/cell
- **计算方法**: HSE06杂化泛函

---

## 计算流程

### 1. ENCUT/KSPACING收敛测试 ✅

**测试结果**：
- **推荐ENCUT**: 550 eV
- **推荐KSPACING**: 0.15 Å⁻¹
- **收敛判据**: ≤1 meV/atom

详细报告见：`convergence_test/Convergence_Report.md`

### 2. PBE静态自洽计算 ✅

**计算参数**：
- ENCUT = 550 eV
- KSPACING = 0.15 Å⁻¹
- KGAMMA = .TRUE.
- ISMEAR = 0, SIGMA = 0.05

**计算结果**：
- 总能量：-35.19847739 eV
- WAVECAR：已生成（22 MB）
- CHGCAR：已生成（3.4 MB）

**文件位置**：`pbe_scf/`

### 3. HSE06高精度计算 ✅

**计算参数**：
- ENCUT = 550 eV（与PBE一致）
- KSPACING = 0.15 Å⁻¹（与PBE一致）
- HFSCREEN = 0.2 Å⁻¹（HSE06标准）
- AEXX = 0.25（精确交换比例）
- ALGO = Damped
- PRECFOCK = Fast

**收敛情况**：
- 迭代次数：11次
- 能量收敛：ΔE = 7.6×10⁻⁶ eV < EDIFF(1×10⁻⁵)
- 总能量：-40.86766716 eV

**文件位置**：`hse_bandgap/`

---

## 带隙结果

### HSE06带隙

| 属性 | 值 |
|------|-----|
| **带隙** | **5.71 eV** |
| **带隙类型** | **间接带隙** |
| **跃迁路径** | K点(0.350, 0.300, 0.000) → Γ点(0.000, 0.000, 0.000) |

### 结果分析

1. **带隙大小**：5.71 eV，属于宽带隙半导体
2. **带隙类型**：间接带隙，导带底在K点附近，价带顶在Γ点
3. **与PBE对比**：PBE通常低估带隙，HSE06显著改善了带隙预测

---

## 关键文件位置

| 文件 | 路径 |
|------|------|
| 收敛测试报告 | `convergence_test/Convergence_Report.md` |
| PBE输入文件 | `pbe_scf/INCAR_pbe` |
| PBE输出 | `pbe_scf/OUTCAR`, `pbe_scf/WAVECAR`, `pbe_scf/CHGCAR` |
| HSE输入文件 | `hse_bandgap/INCAR_hse` |
| HSE参数说明 | `hse_bandgap/HSE_INCAR_explanation.md` |
| HSE输出 | `hse_bandgap/OUTCAR`, `hse_bandgap/vasprun.xml` |

---

## 计算资源

- **硬件**: 8× NVIDIA GeForce RTX 2080 Ti
- **并行方式**: 8卡GPU并行
- **计算时间**: 约20分钟（HSE阶段）

---

## 参数一致性验证

| 参数 | PBE SCF | HSE06 | 一致性 |
|------|---------|-------|--------|
| ENCUT | 550 eV | 550 eV | ✅ |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | ✅ |
| KGAMMA | .TRUE. | .TRUE. | ✅ |
| ISMEAR | 0 | 0 | ✅ |
| SIGMA | 0.05 | 0.05 | ✅ |

---

**生成时间**: 2026-04-20
**计算方法**: HSE06杂化泛函
**收敛状态**: 已收敛
