# Ti 结构优化 INCAR 参数说明

## 材料信息
- **材料**：Ti（钛）
- **结构**：15 原子六角晶系结构
- **类型**：过渡金属

## 参数选择依据

### 展宽参数 (ISMEAR, SIGMA)
- **ISMEAR = 1**：Methfessel-Paxton 一阶展宽，适用于金属体系
- **SIGMA = 0.2**：较大展宽改善费米面附近 K 点采样收敛
- **参考**：VASP Wiki [Number of k points and method for smearing](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 截断能 (ENCUT)
- **ENCUT = 520 eV**：Ti 的 POTCAR ENMAX 约 375 eV，取 1.3 倍约 488 eV
- 为消除 Pulay 应力，取 520 eV 确保足够精度
- **参考**：VASP Wiki [Volume relaxation](https://vasp.at/wiki/Volume_relaxation)

### 离子弛豫参数
- **IBRION = 2**：共轭梯度法 (CG)，最稳健的优化算法
- **ISIF = 3**：全优化（原子位置 + 晶胞形状 + 体积）
- **NSW = 200**：最大离子步数
- **EDIFFG = -0.02**：力收敛标准 0.02 eV/Å
- **POTIM = 0.5**：CG 步长

### K 点设置
- **KSPACING = 0.15**：金属需要较密的 K 点网格
- **KGAMMA = .TRUE.**：包含 Gamma 点

### 其他参数
- **PREC = Accurate**：标准精度
- **ALGO = Normal**：常规迭代算法
- **GGA = PE**：PBE 泛函

## 未进行 ENCUT/KSPACING 收敛测试
本次计算使用经验参数，未进行系统性的 ENCUT/KSPACING 收敛测试。
如需与文献严格可比或用于后续高精度计算（EOS、带隙等），建议先进行收敛测试。
