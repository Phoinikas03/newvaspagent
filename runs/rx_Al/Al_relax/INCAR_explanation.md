# Al 结构松弛 INCAR 参数说明

## 材料类型判断
- **材料**: Al（铝）
- **类型**: 金属
- **结构**: 26 原子超胞（六方晶系）

## 关键参数选择依据

### ISMEAR / SIGMA
- **ISMEAR = 1**: Methfessel-Paxton 一阶展宽，适合金属体系
- **SIGMA = 0.2**: 较大展宽，改善费米面附近 K 点采样收敛
- **参考**: [VASP Wiki: ISMEAR 选择指南](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### ENCUT
- **ENCUT = 520 eV**: Al 的 POTCAR ENMAX 约 240 eV，取 1.3 倍约 312 eV；这里采用 520 eV 确保高精度，消除 Pulay 应力影响
- **参考**: [VASP Wiki: 体积松弛与 Pulay 应力](https://vasp.at/wiki/Volume_relaxation)

### KSPACING
- **KSPACING = 0.15**: 金属体系需要较密的 K 点网格以确保能量和力的收敛
- **KGAMMA = .TRUE.**: 包含 Gamma 点

### 离子弛豫参数
- **IBRION = 2**: 共轭梯度法（CG），最稳健的松弛算法
- **ISIF = 3**: 全松弛（原子位置 + 晶胞形状 + 体积）
- **NSW = 200**: 最大离子步数
- **EDIFFG = -0.02**: 力收敛标准，负值表示力阈值（eV/Å）
- **POTIM = 0.5**: CG 步长

### 其他参数
- **PREC = Accurate**: 标准精度，松弛通常足够
- **ALGO = Normal**: 常规迭代算法
- **GGA = PE**: PBE 泛函

## 并行参数（GPU 优化）
- **KPAR = 8**: 与 GPU 数对齐，k 点并行
- **NCORE**: 未设置（GPU 场景不需要，已删除旧的 CPU 参数）

## 硬件配置
- 8 张 NVIDIA RTX 2080 Ti GPU
- 单节点，无调度系统

## 备注
- 未进行 ENCUT/KSPACING 系统收敛测试，使用经验值
- 非磁性体系，未设置 ISPIN/MAGMOM
- 无强关联元素，未设置 DFT+U