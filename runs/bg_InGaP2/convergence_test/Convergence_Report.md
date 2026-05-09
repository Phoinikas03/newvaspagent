# ENCUT 与 KSPACING 收敛测试报告

## 测试体系
- 材料：InGaP2
- 原子数：4 (In:1, Ga:1, P:2)
- POSCAR 来源：/home/xiazeyu21/newvaspagent/data/bandgap/InGaP2
- 测试类型：静态单点能 (NSW=0)

## ENCUT 收敛测试

固定参数：KSPACING = 0.15 Å⁻¹

| ENCUT (eV) | Total Energy (eV) | ΔE (meV/atom) |
|------------|-------------------|---------------|
| 250 | -17.28028214 | -- |
| 300 | -17.28754470 | -1.8156 |
| 350 | -17.29021725 | -0.6681 |
| 400 | -17.29068485 | -0.1169 |
| 450 | -17.29071399 | -0.0073 |
| 500 | -17.29086454 | -0.0376 |

**结论**：从 ENCUT = 350 eV 开始满足 ≤1 meV/atom 判据。
**推荐值**：**ENCUT = 400 eV**（宁大勿小）

## KSPACING 收敛测试

固定参数：ENCUT = 400 eV

| KSPACING (Å⁻¹) | Total Energy (eV) | ΔE (meV/atom) |
|----------------|-------------------|---------------|
| 0.30 | -17.28511440 | -- |
| 0.25 | -17.28833464 | -0.8051 |
| 0.20 | -17.29022668 | -0.4730 |
| 0.15 | -17.29068485 | -0.1145 |
| 0.10 | -17.29086454 | -0.0449 |

**结论**：从 KSPACING = 0.25 Å⁻¹ 开始满足 ≤1 meV/atom 判据。
**推荐值**：**KSPACING = 0.15 Å⁻¹**（宁小勿大，保证精度）

## 最终推荐参数

| 参数 | 推荐值 |
|------|--------|
| ENCUT | 400 eV |
| KSPACING | 0.15 Å⁻¹ |
| KGAMMA | .TRUE. |

## 测试目录

- ENCUT 测试：`/home/xiazeyu21/newvaspagent/runs/bg_InGaP2/convergence_test/encut_test/`
- KSPACING 测试：`/home/xiazeyu21/newvaspagent/runs/bg_InGaP2/convergence_test/kspacing_test/`

---
*报告生成时间：2026-04-21*
