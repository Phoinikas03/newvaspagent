# SnSe 结构优化 INCAR 参数说明

## 材料特性
- **化学式**: Sn₁₅Se₁₆ (31 atoms)
- **晶系**: 正交晶系 (Orthorhombic)
- **晶格参数**: a=9.40 Å, b=8.25 Å, c=11.66 Å
- **电子结构**: 半导体 (窄带隙 ~0.9-1.2 eV)
- **磁性**: 非磁性

## INCAR 参数选择依据

### 展宽参数 (ISMEAR, SIGMA)
- **ISMEAR = 0**: Gaussian 展宽，适用于半导体/绝缘体
- **SIGMA = 0.05**: 小展宽值，避免人工展宽污染价带顶/导带底附近的真实电子态
- **参考**: VASP Wiki [Number of k points and method for smearing](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 弛豫参数 (IBRION, ISIF, NSW, EDIFFG, POTIM)
- **IBRION = 2**: 共轭梯度法 (CG)，最稳健的优化算法
- **ISIF = 3**: 全弛豫，同时优化原子位置、晶胞形状和体积
- **NSW = 200**: 最大离子步数，对于 31 原子体系足够
- **EDIFFG = -0.02**: 力收敛标准 0.02 eV/Å
- **POTIM = 0.5**: CG 步长

### 截断能 (ENCUT)
- **ENCUT = 520 eV**: 取 POTCAR 中最大 ENMAX × 1.3
- **目的**: 消除晶胞体积变化时的 Pulay 应力
- **参考**: VASP Wiki [Volume relaxation](https://vasp.at/wiki/Volume_relaxation)

### K 点设置 (KSPACING, KGAMMA)
- **KSPACING = 0.20 Å⁻¹**: 自动生成 K 点网格
- **KGAMMA = .TRUE.**: 包含 Γ 点

### 其他参数
- **PREC = Accurate**: 标准精度，避免基组截断误差
- **ALGO = Normal**: 常规迭代算法
- **GGA = PE**: PBE 泛函

## 未做系统收敛测试
本次计算未进行 ENCUT 和 KSPACING 的系统收敛测试，使用模板默认值。
如需更高精度或与文献严格可比，建议先运行 convergence skill。
