# BaTiO3 结构松弛 INCAR 参数说明

## 材料分类
- **化学式**：BaTiO3（钙钛矿型氧化物）
- **电子结构**：绝缘体/半导体，含Ti的d轨道强关联
- **晶体结构**：立方钙钛矿（或四方相，取决于温度）

## 关键参数选择依据

### 1. 展宽方法（ISMEAR / SIGMA）
- **ISMEAR = 0**（Gaussian展宽）
  - 原因：BaTiO3是绝缘体，带隙 > 2 eV，Gaussian展宽最安全
  - 避免Methfessel-Paxton（ISMEAR=1）对绝缘体的人工污染
- **SIGMA = 0.05**
  - 原因：绝缘体标准值，足够小以避免展宽对价带顶/导带底的影响

### 2. DFT+U 修正（LDAU / LDAUU）
- **LDAU = .TRUE.**
  - 原因：Ti的d轨道具有强关联特性，需要Hubbard U修正以改善带隙和电子结构描述
- **LDAUTYPE = 2**（Dudarev方法）
  - 最常用的DFT+U实现，仅需提供有效值Ueff = U - J
- **LDAUL = -1 2 -1**
  - Ba(s/p)：-1（不需要U修正）
  - Ti(d)：2（d轨道，l=2）
  - O(s/p)：-1（不需要U修正）
- **LDAUU = 0.0 4.2 0.0**
  - Ti的Ueff = 4.2 eV（参考Materials Project对TiO2的标准值）
  - 该值在文献中广泛应用于钛酸盐化合物

### 3. 离子松弛（IBRION / ISIF / NSW / EDIFFG）
- **IBRION = 2**（共轭梯度CG）
  - 原因：稳健的优化算法，适合初始结构的全面松弛
- **ISIF = 3**（原子位置 + 晶胞形状 + 体积）
  - 原因：块体材料的标准全松弛，允许晶胞自由变化以达到最低能量
- **NSW = 200**
  - 原因：BaTiO3结构相对复杂（39原子），200步通常足够收敛
- **EDIFFG = -0.02**（力收敛标准）
  - 原因：标准精度，最大原子力应 < 0.02 eV/Å
  - 若需更高精度可改为 -0.01

### 4. 截断能与K点网格
- **ENCUT = 520 eV**
  - 原因：使用模板默认值，未进行系统收敛测试
  - 建议值：POTCAR中最大ENMAX的1.3倍（通常在400~520范围）
- **KSPACING = 0.20 Å⁻¹**
  - 原因：使用模板默认值，对绝缘体通常足够
  - 对应K点网格密度约为 Γ点周围 0.20 Å⁻¹ 间距
- **KGAMMA = .TRUE.**
  - 原因：包含Γ点，改善K点采样对称性

## 计算策略
- **未进行ENCUT/KSPACING收敛测试**：直接使用模板参数
- **预期收敛时间**：取决于计算资源，通常需要数小时至数十小时
- **后续步骤**：松弛完成后检查离子步收敛状态，若未收敛则将CONTCAR复制为POSCAR续算

## 参考文献
- Materials Project GGA+U参数：https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values
- VASP官方K点与展宽指南：https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing
- VASP体积松弛指南：https://vasp.at/wiki/Volume_relaxation
