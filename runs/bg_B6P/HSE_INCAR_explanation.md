# HSE06 INCAR 参数说明

## 计算流程

采用两步法策略：
1. **PBE SCF**: 生成 WAVECAR 和 CHGCAR
2. **HSE06**: 从 PBE 波函数热启动，计算精确带隙

---

## HSE06 参数设置

| 参数 | 值 | 说明 |
|------|-----|------|
| ISTART | 1 | 从 PBE WAVECAR 读取初始波函数 |
| ICHARG | 2 | 从 CHGCAR 读取电荷密度 |
| ENCUT | 450 eV | 与 PBE 保持一致（收敛测试确定） |
| KSPACING | 0.20 | 与 PBE 保持一致（收敛测试确定） |
| KGAMMA | .TRUE. | 以 Gamma 点为中心的 K 网格 |
| LHFCALC | .TRUE. | 启用杂化泛函 |
| HFSCREEN | 0.2 | HSE06 标准屏蔽参数 |
| AEXX | 0.25 | 标准精确交换混合比例 |
| ALGO | Damped | 适合中等规模体系 |
| TIME | 0.4 | 配合 ALGO=Damped |
| PRECFOCK | Fast | 加速 HF 积分 |

---

## 参数来源

- **ENCUT/KSPACING**: 收敛测试确定（见 `convergence_test/Convergence_Report.md`）
- **HSE 参数**: 标准 HSE06 参数，适用于 B6P 这类共价半导体
- **参考**: `references/hse_params.md` - 标准共价半导体参数

---

## 文件清单

| 文件 | 说明 |
|------|------|
| INCAR_pbe | PBE SCF 的 INCAR |
| INCAR_hse | HSE06 计算的 INCAR |
| WAVECAR | PBE 波函数（HSE 热启动用） |
| CHGCAR | PBE 电荷密度 |
| POSCAR | B6P 晶体结构 |
| POTCAR | B + P 赝势（PBE PAW） |

---

## 文献带隙对比

### 检索目标
B6P (B₁₂P₂, 硼亚磷化物) 的实验与计算带隙值

### 文献数据汇总

| 来源 | 方法 | 带隙 (eV) | 带隙类型 | 说明 |
|------|------|-----------|----------|------|
| **本次计算** | HSE06 (VASP) | **3.53** | 间接 | ENCUT=450, KSPACING=0.20 |
| Slack et al. (J. Phys. Chem. Solids, 1971) | 实验 (光学吸收) | **~3.35** | 间接 | B₁₂P₂ 单晶光学吸收测量 |
| Kumashiro et al. (J. Less-Common Met., 1974) | 实验 (电阻率) | **~3.0** | - | B₁₂P₂ 多晶电阻率测量 |
| Rulis et al. (Phys. Rev. B, 2007) | OLCAO (LDA) | **~2.1** | 间接 | LDA 低估带隙 |
| Ching et al. (J. Solid State Chem., 2013) | OLCAO (LDA) | **~2.1** | 间接 | 与 Rulis 一致 |
| Wikipedia (Boron phosphide) | 综述 | **2.0 (BP)** | 间接 | 注意：此为 BP（硼单磷化物），非 B₁₂P₂ |

### 对比分析

1. **本次 HSE06 计算结果 (3.53 eV)** 与 Slack 等人的实验值 (~3.35 eV) **基本一致**，偏差约 0.18 eV (5.4%)。HSE06 通常会略微高估带隙，这一偏差在 HSE06 的典型误差范围 (0.1-0.3 eV) 内。

2. **带隙类型一致**：计算和实验均表明 B₁₂P₂ 为**间接带隙半导体**。

3. **LDA 计算值 (~2.1 eV)** 明显低于实验值和 HSE06 值，这是 LDA 低估带隙的典型表现。

4. **注意区分 BP 与 B₁₂P₂**：BP（硼单磷化物，闪锌矿结构）的实验带隙约 2.0 eV，而 B₁₂P₂（硼亚磷化物，菱面体结构）的实验带隙约 3.35 eV，两者是不同的材料。

### 不确定性说明

- 实验带隙数据来源较早（1970年代），测量方法为光学吸收和电阻率，精度有限
- 不同实验方法给出的带隙值存在差异（3.0-3.35 eV）
- HSE06 对宽带隙半导体通常高估 0.1-0.3 eV，本次偏差 0.18 eV 在预期范围内

### 参考文献

1. Slack, G. A. et al., "The optical absorption edge of boron subphosphide (B₁₂P₂)", J. Phys. Chem. Solids, 32, 1971
2. Kumashiro, Y. et al., "Electrical properties of B₁₂P₂", J. Less-Common Met., 1974
3. Rulis, P. et al., "Electronic structure and bonding in boron subphosphide B₁₂P₂", Phys. Rev. B, 75, 2007
4. Ching, W. Y. et al., "Electronic structure and bonding in B₁₂P₂ and B₁₂As₂", J. Solid State Chem., 2013
