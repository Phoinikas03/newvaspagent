# Convergence Report — Cu2O

**日期**：2026-04-21
**结构**：Cu2O（Cu4O2 单胞），立方结构，a = 4.247 Å
**POTCAR**：Cu（ENMAX = 295.4 eV），O（ENMAX = 400.0 eV）
**ISMEAR / SIGMA**：0 / 0.05（Gaussian 展宽，半导体）
**PREC**：Accurate

---

## 1. ENCUT 收敛测试

固定 KSPACING = 0.15 Å⁻¹，扫描 ENCUT。

| ENCUT (eV) | E_total (eV)     | ΔE (meV/atom) | 收敛? |
|------------|------------------|---------------|-------|
| 400        | -27.24191139     | —             | —     |
| 450        | -27.20690167     | 5.83          | ✗     |
| 500        | -27.19880850     | 1.35          | ✗     |
| 550        | -27.20115558     | -0.39         | ✓     |
| 600        | -27.20449948     | -0.56         | ✓     |

**收敛 ENCUT = 500 eV**（在 500→550 eV 时 ΔE = -0.39 meV/atom，满足 ≤ 1 meV/atom 判据）

---

## 2. KSPACING 收敛测试

固定 ENCUT = 500 eV，扫描 KSPACING。

| KSPACING (Å⁻¹) | E_total (eV)     | ΔE (meV/atom) | 收敛? |
|----------------|------------------|---------------|-------|
| 0.30           | -27.19528601     | —             | —     |
| 0.25           | -27.19747229     | -0.36         | ✓     |
| 0.20           | -27.19860677     | -0.19         | ✓     |
| 0.15           | -27.19880850     | -0.03         | ✓     |
| 0.10           | -27.19883453     | -0.00         | ✓     |

**收敛 KSPACING = 0.30 Å⁻¹**（在 0.30→0.25 时 ΔE = -0.36 meV/atom）

**注**：为提高带隙计算精度，推荐使用 **KSPACING = 0.20 Å⁻¹**

---

## 3. 推荐生产参数

| 参数 | 推荐值 |
|------|--------|
| ENCUT | **500 eV** |
| KSPACING | **0.20 Å⁻¹** |
| KGAMMA | .TRUE. |

---

## 4. 文件位置

- POSCAR: `/mnt/data_x3/xiazeyu/newvaspagent/runs/bg_Cu2O/POSCAR`
- POTCAR: `/mnt/data_x3/xiazeyu/newvaspagent/runs/bg_Cu2O/POTCAR`
- ENCUT 测试目录: `convergence_test/encut_test/`
- KSPACING 测试目录: `convergence_test/kspacing_test/`
