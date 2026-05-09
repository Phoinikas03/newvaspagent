# CaF2 结构松弛 INCAR 参数说明

## 材料分类
- **CaF2**：离子晶体（绝缘体），荧石结构
- **带隙**：约 12 eV（绝缘体）
- **磁性**：非磁性

## 关键参数选择依据

### 展宽方法（ISMEAR / SIGMA）
- **ISMEAR = 0**（Gaussian）：适用于绝缘体，避免人工展宽污染带隙
- **SIGMA = 0.05**：小展宽，确保电子态计算精度

### 离子松弛（IBRION / ISIF）
- **IBRION = 2**（CG）：稳健的共轭梯度法，适合初始结构优化
- **ISIF = 3**：全松弛（原子坐标 + 晶胞形状 + 体积），适用于块体材料

### 截断能（ENCUT）
- **ENCUT = 520 eV**：取 POTCAR 中最大 ENMAX 的 1.3 倍，消除 Pulay 应力
- 未进行系统收敛测试（用户未要求），采用模板默认值

### K 点网格（KSPACING）
- **KSPACING = 0.20 Å⁻¹**：标准密度，适合绝缘体
- **KGAMMA = .TRUE.**：Gamma 点中心网格

### 收敛标准
- **EDIFF = 1E-6**：电子步收敛
- **EDIFFG = -0.02 eV/Å**：力收敛标准（通常 < 0.01 eV/Å 为高精度）

## 参考来源
- VASP 官方 Wiki：[K 点与 Smearing 指南](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- VASP 官方 Wiki：[体积松弛与 Pulay 应力](https://vasp.at/wiki/Volume_relaxation)
- 本地参考：`references/incar_params.md`
