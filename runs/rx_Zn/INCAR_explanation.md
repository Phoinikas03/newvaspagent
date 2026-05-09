# Zn 结构松弛 INCAR 参数说明

## 材料类型
**Zn（锌）是金属**

## 关键参数选择依据

### ISMEAR / SIGMA
- **ISMEAR = 1**：Methfessel-Paxton 一阶展宽，适合金属体系
- **SIGMA = 0.2**：较大展宽改善费米面附近 K 点采样收敛
- 参考：[VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### ENCUT
- **ENCUT = 520 eV**：Zn 的 POTCAR ENMAX 约 300 eV，取 1.3 倍约 400 eV
- 设为 520 eV 以消除 Pulay 应力，保证体积松弛精度
- 参考：[VASP Wiki: 体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)

### ISIF
- **ISIF = 3**：全松弛（原子位置 + 晶胞形状 + 体积）
- 适用于块体材料的标准结构优化

### IBRION / POTIM
- **IBRION = 2**：共轭梯度法（CG），最稳健
- **POTIM = 0.5**：CG 步长

### KSPACING
- **KSPACING = 0.15**：金属用较密 K 点网格
- **KGAMMA = .TRUE.**：包含 Gamma 点

### 磁性
- Zn 无磁性，不需要设置 ISPIN 和 MAGMOM

### DFT+U
- Zn 无强关联 d 电子，不需要 DFT+U

## 收敛测试
- 未进行 ENCUT/KSPACING 系统收敛测试
- 使用经验参数，适用于一般结构优化

## 参考
- [VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- [VASP Wiki: 体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)
- [VASP Wiki: 离子松弛算法 (IBRION)](https://vasp.at/wiki/IBRION)
