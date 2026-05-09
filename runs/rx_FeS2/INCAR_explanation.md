# FeS2 结构优化 INCAR 参数说明

## 材料特性
- **化学式**：FeS₂（黄铁矿）
- **结构**：立方晶系，空间群 Pa-3
- **电子性质**：半导体（带隙 ~0.95 eV）
- **磁性**：非磁性（Fe²⁺ 低自旋配置）

## 关键参数选择依据

### 电子结构参数
| 参数 | 值 | 说明 |
|------|-----|------|
| ENCUT | 520 eV | 取 POTCAR 中最大 ENMAX 的 1.3 倍，消除 Pulay 应力 |
| EDIFF | 1E-6 | 电子步收敛标准，确保力的精度 |
| PREC | Accurate | 标准精度，适合结构优化 |

### 展宽方法（ISMEAR / SIGMA）
- **ISMEAR = 0**（Gaussian 展宽）：FeS₂ 为半导体，禁止使用 ISMEAR=1（Methfessel-Paxton）
- **SIGMA = 0.05**：小展宽，避免人工展宽污染价带顶/导带底附近的真实电子态
- 参考：`relax/references/incar_params.md` §ISMEAR / SIGMA 选择指南

### 离子弛豫参数
| 参数 | 值 | 说明 |
|------|-----|------|
| IBRION | 2 | 共轭梯度法（CG），最稳健 |
| ISIF | 3 | 全优化：原子位置 + 晶胞形状 + 体积 |
| NSW | 100 | 最大离子步数，通常足够 |
| EDIFFG | -0.02 | 力收敛阈值 0.02 eV/Å |
| POTIM | 0.5 | CG 步长 |

### K 点网格
- **KSPACING = 0.30**：半导体材料推荐密度
- **KGAMMA = .TRUE.**：Gamma 点中心网格

### 不使用的修正
- **无 DFT+U**：FeS₂ 中 Fe 为 d⁶ 配置（Fe²⁺），标准 GGA-PBE 足够
- **无 vdW 修正**：FeS₂ 为离子化合物，范德瓦尔斯相互作用不显著
- **无磁性设置**：FeS₂ 非磁性

## 文献参考
- Materials Project (mp-226): FeS₂ pyrite structure
- arXiv:2311.06135: Thermoelectric transport properties of electron doped pyrite FeS₂
- VASP Wiki: [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- VASP Wiki: [体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)

## 计算策略
- **未进行 ENCUT/KSPACING 收敛测试**：直接采用推荐参数进行结构优化
- **预期收敛**：离子步通常在 50-80 步内收敛
- **后续计算**：优化完成后可进行能带结构（HSE）或其他性质计算
