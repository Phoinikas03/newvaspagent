# Li2S 结构优化 INCAR 参数说明

## 材料类型判断

**Li2S（硫化锂）** 是一种宽禁带半导体/绝缘体材料：
- 带隙约 2-3 eV（实验值）
- 离子化合物，Li⁺ 和 S²⁻
- 无磁性，无需设置 ISPIN/MAGMOM
- 无强关联 d/f 轨道，无需 DFT+U
- 无层状结构或弱相互作用，无需 vdW 修正

## 关键参数选择依据

### 展宽参数 (ISMEAR / SIGMA)
- **ISMEAR = 0**：Gaussian 展宽，适合半导体/绝缘体
- **SIGMA = 0.05**：小展宽避免人工展宽污染价带顶/导带底

参考：[VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)

### 弛豫参数 (IBRION / ISIF / NSW)
- **IBRION = 2**：共轭梯度法 (CG)，最稳健的离子优化算法
- **ISIF = 3**：全弛豫（原子位置 + 晶胞形状 + 体积），块体材料标准设置
- **NSW = 200**：最大离子步数，Li2S 结构简单应足够
- **EDIFFG = -0.02**：力收敛标准 0.02 eV/Å

参考：[VASP Wiki: 离子松弛算法 (IBRION)](https://vasp.at/wiki/IBRION)

### 截断能 (ENCUT)
- **ENCUT = 520 eV**：取 POTCAR 中最大 ENMAX × 1.3
- Li 的 ENMAX ≈ 260 eV，S 的 ENMAX ≈ 400 eV
- 520 eV > 400 × 1.3 = 520 eV，满足 Pulay 应力消除要求

参考：[VASP Wiki: 体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)

### K 点设置 (KSPACING / KGAMMA)
- **KSPACING = 0.20 Å⁻¹**：对应约 6×6×6 的 k 网格
- **KGAMMA = .TRUE.**：包含 Gamma 点
- Li2S 晶胞约 7×7×8 Å³，k 点密度足够

### GPU 并行参数 (KPAR)
- **KPAR = 8**：与 8 GPU 对齐，k 点并行
- **不设置 NCORE**：GPU 场景下避免 CPU 并行参数干扰

## 未进行 ENCUT/KSPACING 收敛测试

本次计算使用模板默认参数，未进行系统的 ENCUT/KSPACING 收敛测试（1 meV/atom 标准）。
若后续需要进行高精度能量比较（如 EOS、带隙、吸附能等），建议先进行收敛测试。

## 参数来源

- 本地参考文档：`references/incar_params.md`
- VASP 官方 Wiki
- Materials Project 推荐值
