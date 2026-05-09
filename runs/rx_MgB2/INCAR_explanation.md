# MgB₂ 结构优化 INCAR 参数说明

## 材料体系
- **化学式**：MgB₂（二硼化镁）
- **晶体结构**：六方晶系，P6/mmm 空间群（AlB₂ 型结构）
- **电子结构**：金属（超导体，Tc ≈ 39 K）

## 关键参数选择依据

### ISMEAR / SIGMA
- **ISMEAR = 1**：Methfessel-Paxton 一阶展宽，适用于金属体系
- **SIGMA = 0.2**：较大展宽改善 K 点收敛，金属体系标准值
- **参考**：VASP Wiki [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### ENCUT
- **ENCUT = 450 eV**：取 POTCAR 中最大 ENMAX × 1.3
  - B: ENMAX ≈ 319 eV
  - Mg: ENMAX ≈ 223 eV
  - 推荐：319 × 1.3 ≈ 415 eV，取 450 eV 留有余量
- **参考**：VASP Wiki [体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)

### KSPACING
- **KSPACING = 0.15 Å⁻¹**：金属需较密 K 点网格
- 对应约 12×12×12 的网格（基于晶格常数 a ≈ 3.1 Å, c ≈ 3.5 Å）

### ISIF
- **ISIF = 3**：全弛豫（原子位置 + 晶胞形状 + 体积）
- 适用于块体材料的标准结构优化

### IBRION / POTIM
- **IBRION = 2**：共轭梯度法（CG），最稳健
- **POTIM = 0.5**：CG 步长

### EDIFF / EDIFFG
- **EDIFF = 1E-6**：电子步收敛标准
- **EDIFFG = -0.01**：力收敛阈值 0.01 eV/Å（高精度）

### NCORE
- **NCORE = 4**：8 GPU 并行设置

## 文献参考
1. Buzea C., Yamashita T. "Review of superconducting properties of MgB2", Supercond. Sci. Technol. 14 (2001) R115-R146. [arXiv:cond-mat/0108265](https://arxiv.org/pdf/cond-mat/0108265v2.pdf)
2. 实验晶格常数：a = 3.086 Å, c = 3.524 Å（室温）

## 备注
- 未进行系统 ENCUT/KSPACING 收敛测试
- 参数基于文献经验值与 VASP 官方推荐
