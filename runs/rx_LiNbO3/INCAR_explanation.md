# LiNbO3 结构松弛 INCAR 参数说明

## 材料信息
- **化学式**: LiNbO3（铌酸锂）
- **结构**: 铁电钙钛矿结构
- **原子数**: 39 (Li₇Nb₈O₂₄)
- **电子结构**: 宽带隙绝缘体（带隙 ~3.7-4 eV）

## 参数选择依据

### 展宽方法 (ISMEAR/SIGMA)
- **ISMEAR = 0**: Gaussian 展宽
- **SIGMA = 0.05**: 小展宽值
- **依据**: LiNbO3 为宽带隙绝缘体，使用 Gaussian 展宽避免人工展宽污染价带顶/导带底附近的真实电子态
- **参考**: `references/incar_params.md` - 半导体/绝缘体推荐值

### 截断能 (ENCUT)
- **ENCUT = 520 eV**
- **依据**: Nb 元素 POTCAR ENMAX ≈ 400 eV，取 1.3 倍以消除晶胞体积变化时的 Pulay 应力
- **参考**: VASP 官方体积松弛指南 (https://vasp.at/wiki/Volume_relaxation)

### K 点网格 (KSPACING)
- **KSPACING = 0.20 Å⁻¹**
- **依据**: 绝缘体标准密度，约 5-6 K 点/方向，对绝缘体已足够
- **未做系统收敛测试**: 使用模板默认值

### 离子弛豫参数
- **IBRION = 2**: 共轭梯度法 (CG)，最稳健的优化算法
- **ISIF = 3**: 全松弛（原子位置 + 晶胞形状 + 体积），块体材料标准选择
- **NSW = 200**: 最大离子步数
- **EDIFFG = -0.02**: 力收敛标准 0.02 eV/Å
- **POTIM = 0.5**: CG 步长

### 其他参数
- **PREC = Accurate**: 标准精度，避免基组截断误差
- **ALGO = Normal**: 常规迭代算法
- **GGA = PE**: PBE 泛函

## 未使用的参数（不适用）
- **ISPIN/MAGMOM**: LiNbO3 非磁性
- **LDAU/LDAUU**: Nb⁵⁺ 为 d⁰ 电子构型，d 轨道全空，无需 DFT+U
- **IVDW**: 无显著 van der Waals 相互作用

## 备注
- **收敛测试**: 未进行 ENCUT/KSPACING 系统收敛测试，使用模板默认参数
- 若后续需要进行高精度计算（EOS、带隙等），建议先进行收敛测试
