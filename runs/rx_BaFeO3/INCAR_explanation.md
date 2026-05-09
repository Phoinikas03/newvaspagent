# BaFeO3 结构松弛 INCAR 参数说明

## 材料分类
- **化学式**：BaFeO3（钙钛矿氧化物）
- **电子结构**：绝缘体/半导体，含磁性 Fe(3+)
- **关键特征**：强关联 d 轨道，需要 DFT+U 修正

## 关键参数选择依据

### 1. 自旋极化与磁矩（ISPIN / MAGMOM）
- **ISPIN = 2**：启用自旋极化计算，适用于磁性体系
- **MAGMOM = 7*0 8*5 24*0**：
  - Ba：非磁性，初始磁矩 = 0
  - Fe：高自旋 Fe(3+)，初始磁矩 = 5.0 μB（参考文献标准值）
  - O：非磁性，初始磁矩 = 0
- **参考**：Materials Project 数据库中 Fe 氧化物的标准设置

### 2. DFT+U 修正（LDAU / LDAUU）
- **LDAU = .TRUE.**：启用 Hubbard U 修正
- **LDAUTYPE = 2**：Dudarev 方法（最常用，仅需 Ueff = U - J）
- **LDAUL = -1 2 -1**：
  - Ba：-1（s/p 轨道，不需要 U 修正）
  - Fe：2（d 轨道，需要 U 修正）
  - O：-1（s/p 轨道，不需要 U 修正）
- **LDAUU = 0 5.3 0**（eV）：
  - Fe 的有效 U 值 = 5.3 eV（参考 Materials Project 数据库对 Fe 氧化物的推荐值）
  - 该值改善了 Fe d 轨道的自相互作用误差，提高了带隙和晶格常数的计算精度
- **参考**：
  - Materials Project Hubbard U Values: https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values
  - 文献中 Fe 氧化物（FeO, Fe₂O₃）的 Ueff 范围：4.0~5.3 eV

### 3. 展宽方法（ISMEAR / SIGMA）
- **ISMEAR = 0**：Gaussian 展宽，适用于绝缘体/半导体
- **SIGMA = 0.05**：小展宽值，避免人工展宽污染价带顶/导带底附近的真实电子态
- **理由**：BaFeO3 预期为绝缘体，不应使用金属展宽方法（ISMEAR=1）

### 4. 离子松弛参数
- **IBRION = 2**：共轭梯度法（CG），最稳健的优化算法
- **ISIF = 3**：同时优化原子位置、晶胞形状和体积（全松弛）
- **NSW = 200**：最大离子步数，足以收敛大多数氧化物
- **EDIFFG = -0.02**：力收敛标准 0.02 eV/Å，标准精度
- **POTIM = 0.5**：CG 步长，平衡收敛速度和稳定性

### 5. 截断能（ENCUT）
- **ENCUT = 520 eV**：取 POTCAR 中所有元素最大 ENMAX 的 1.3 倍
- **目的**：消除晶胞体积变化时的 Pulay 应力，确保体积松弛的准确性
- **参考**：VASP 官方体积松弛指南

### 6. K 点网格（KSPACING / KGAMMA）
- **KSPACING = 0.20 Å⁻¹**：自动生成 K 点网格，密度适中
- **KGAMMA = .TRUE.**：Gamma 点中心网格，改善对称性
- **说明**：INCAR 中设置 KSPACING 时，setup_vasp_inputs 不会生成 KPOINTS 文件

## 计算流程
1. 从头开始（ISTART=0）
2. 电子步收敛至 1E-6 eV
3. 离子步收敛至最大力 < 0.02 eV/Å
4. 输出最终结构（CONTCAR）、能量和力

## 后续建议
- 若离子步未收敛（NSW 达到上限），将 CONTCAR 复制为 POSCAR 续算
- 若需要更高精度的能带结构或带隙，可在松弛后进行 HSE 计算（参考 bandgap skill）
- 若需要验证 ENCUT 和 KSPACING 的收敛性，可使用 convergence skill 进行静态单点收敛测试

## 参考文献与链接
- VASP Wiki: K 点数量与 Smearing 展宽方法指导
  https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing
- VASP Wiki: 体积松弛与 Pulay 应力消除
  https://vasp.at/wiki/Volume_relaxation
- Materials Project: GGA+U 计算中 U 值的选取方法与列表
  https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values
