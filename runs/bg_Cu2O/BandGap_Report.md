# Cu2O 能带计算报告

**计算日期**：2026-04-21
**结构**：Cu2O（Cu4O2 单胞），立方结构，a = 4.247 Å

---

## 1. 收敛测试结果

### ENCUT 收敛测试
- 固定 KSPACING = 0.15 Å⁻¹
- 测试范围：400-600 eV
- **收敛 ENCUT = 500 eV**（ΔE = -0.39 meV/atom ≤ 1 meV/atom）

### KSPACING 收敛测试
- 固定 ENCUT = 500 eV
- 测试范围：0.10-0.30 Å⁻¹
- **收敛 KSPACING = 0.20 Å⁻¹**

---

## 2. PBE SCF 计算

| 参数 | 值 |
|------|-----|
| ENCUT | 500 eV |
| KSPACING | 0.20 Å⁻¹ |
| KPAR | 2 |
| GPU 数量 | 2 |
| **总能量** | **-27.19860677 eV** |

---

## 3. HSE06 计算

| 参数 | 值 |
|------|-----|
| ENCUT | 500 eV |
| KSPACING | 0.20 Å⁻¹ |
| KPAR | 8 |
| GPU 数量 | 8 |
| ALGO | Damped |
| HFSCREEN | 0.2 |
| AEXX | 0.25 |
| **总能量** | **-31.66292142 eV** |

---

## 4. 带隙结果

| 属性 | 值 |
|------|-----|
| **带隙** | **2.046 eV** |
| 类型 | 直接带隙 |
| 跃迁路径 | Γ → Γ |

---

## 5. 与实验对比

| 来源 | 带隙 (eV) |
|------|-----------|
| 本次 HSE06 计算 | 2.046 |
| 实验值 | ~2.0-2.2 |

**结论**：HSE06 计算结果与实验值符合良好！

---

## 6. 文件位置

```
/mnt/data_x3/xiazeyu/newvaspagent/runs/bg_Cu2O/
├── POSCAR                          # 源结构文件
├── POTCAR                          # 赝势文件
├── convergence_test/
│   ├── Convergence_Report.md       # 收敛测试报告
│   ├── encut_test/                 # ENCUT 测试
│   └── kspacing_test/              # KSPACING 测试
├── pbe_scf/
│   ├── INCAR_pbe                   # PBE INCAR 备份
│   ├── WAVECAR                     # PBE 波函数
│   ├── CHGCAR                      # PBE 电荷密度
│   └── OUTCAR                      # PBE 输出
└── hse_calc/
    ├── INCAR_hse                   # HSE INCAR 备份
    ├── vasprun.xml                 # HSE 输出 XML
    └── OUTCAR                      # HSE 输出
```
