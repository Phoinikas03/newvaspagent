# LiFeAs 结构松弛 INCAR 参数说明

## 材料体系
- **化学式**: LiFeAs
- **结构类型**: 四方晶系铁基超导体
- **原子数**: 23 个原子（7 Li + 8 Fe + 8 As）

## 电子结构分类
- **类型**: 金属（铁基超导体）
- **磁性**: 含 Fe 元素，需考虑自旋极化

## 关键参数选择依据

### ISMEAR / SIGMA
- **ISMEAR = 1**: Methfessel-Paxton 一阶展宽，适合金属体系
- **SIGMA = 0.2**: 较大展宽改善费米面附近 K 点收敛
- **参考**: VASP Wiki [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### ISPIN / MAGMOM
- **ISPIN = 2**: 自旋极化计算，考虑 Fe 的磁性
- **MAGMOM**: Li(0.0) × 7 + Fe(5.0) × 8 + As(0.0) × 8
- Fe 初始磁矩取 5.0 μB（参考 incar_params.md 磁性材料推荐值）

### ENCUT
- **值**: 520 eV
- **依据**: As 的 ENMAX ≈ 349 eV (PBE)，取 1.3× ≈ 454 eV，向上取整到 520 eV
- **目的**: 消除晶胞体积变化时的 Pulay 应力

### KSPACING
- **值**: 0.15 Å⁻¹
- **依据**: 金属体系需要较密的 K 点网格以保证能量收敛

### ISIF
- **值**: 3
- **含义**: 同时优化原子位置、晶胞形状和体积
- **适用**: 块体材料标准全弛豫

### IBRION / POTIM
- **IBRION = 2**: 共轭梯度法（CG），最稳健
- **POTIM = 0.5**: CG 步长

### EDIFFG
- **值**: -0.02 eV/Å
- **含义**: 力收敛阈值，负值表示力收敛标准

## 收敛测试状态
- **ENCUT/KSPACING 收敛**: 未执行
- **说明**: 本次计算使用经验参数，若需与文献严格可比或用于后续 EOS/带隙计算，建议先执行 convergence skill

## 参考来源
- VASP Wiki: [Volume Relaxation](https://vasp.at/wiki/Volume_relaxation)
- VASP Wiki: [IBRION](https://vasp.at/wiki/IBRION)
- 本地参考: `references/incar_params.md`
