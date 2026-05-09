# BN ENCUT与KSPACING收敛测试报告

## 测试体系
- **材料**: BN (六方晶系，类石墨结构)
- **原子数**: 4 atoms/cell
- **收敛判据**: 相邻测试步能量差 ≤ 1 meV/atom

---

## 1. ENCUT收敛测试

**固定参数**:
- KSPACING = 0.15 Å⁻¹
- KGAMMA = .TRUE.
- ISMEAR = 0, SIGMA = 0.05

**测试结果**:

| ENCUT (eV) | Total Energy (eV) | ΔE (meV/atom) |
|------------|-------------------|---------------|
| 300        | -35.17443946      | --            |
| 350        | -35.14784021      | +6.650        |
| 400        | -35.18663547      | -9.699        |
| 450        | -35.19983195      | -3.299        |
| 500        | -35.19752108      | +0.578        |
| 550        | -35.19847739      | -0.239        |

**收敛判定**:
- ENCUT=500→550: ΔE = -0.239 meV/atom ✅ (满足 ≤1 meV/atom)
- ENCUT=450→500: ΔE = +0.578 meV/atom ✅ (满足 ≤1 meV/atom)

**推荐值**: **ENCUT = 550 eV**

---

## 2. KSPACING收敛测试

**固定参数**:
- ENCUT = 550 eV
- KGAMMA = .TRUE.
- ISMEAR = 0, SIGMA = 0.05

**测试结果**:

| KSPACING (Å⁻¹) | Total Energy (eV) | ΔE (meV/atom) |
|----------------|-------------------|---------------|
| 0.30           | -35.19847420      | --            |
| 0.25           | -35.19848245      | -0.002        |
| 0.20           | -35.19845978      | +0.006        |
| 0.15           | -35.19847739      | -0.004        |
| 0.10           | -35.19847950      | -0.001        |

**收敛判定**:
- 所有相邻步ΔE均远小于1 meV/atom ✅
- 最大ΔE仅为0.006 meV/atom

**推荐值**: **KSPACING = 0.15 Å⁻¹**
- 理由：已完全收敛，计算成本适中

---

## 3. 最终推荐参数

用于后续PBE和HSE能带计算：

```
ENCUT    = 550    # eV
KSPACING = 0.15   # Å⁻¹
KGAMMA   = .TRUE.
```

**重要提示**:
- PBE和HSE两阶段必须使用**完全相同**的ENCUT和KSPACING
- 确保工作目录下不存在KPOINTS文件（使用INCAR中的KSPACING自动生成K点）

---

## 4. 测试文件位置

- ENCUT测试目录: `convergence_test/encut_test/e_*/`
- KSPACING测试目录: `convergence_test/kspacing_test/k_*/`
- 本报告: `convergence_test/Convergence_Report.md`

---

**生成时间**: 2026-04-20
**计算资源**: 8× NVIDIA GeForce RTX 2080 Ti (GPU并行)
