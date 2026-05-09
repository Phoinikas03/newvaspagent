# Bi₂Te₃ 结构松弛 INCAR 参数说明

## 材料特性

- **化学式**：Bi₂Te₃
- **晶体结构**：层状结构，Te-Bi-Te-Bi-Te 五原子层单元
- **电子结构**：窄带隙半导体（带隙约 0.15-0.3 eV），拓扑绝缘体
- **磁性**：非磁性
- **特殊相互作用**：层间存在弱的范德华相互作用

## 关键参数选择依据

### ISMEAR / SIGMA
- **ISMEAR = 0**：Gaussian 展宽，半导体/绝缘体的标准选择
- **SIGMA = 0.05**：小展宽值，避免人工展宽污染价带顶/导带底附近的真实电子态
- **参考**：`references/incar_params.md` - 半导体/绝缘体章节

### IVDW
- **IVDW = 12**：DFT-D3(BJ) 阻尼校正
- **原因**：Bi₂Te₃ 是层状材料，层间存在弱的范德华相互作用，标准 PBE 泛函无法准确描述这种弱相互作用，需要 vdW 修正
- **参考**：`references/incar_params.md` - 含 Van der Waals 弱相互作用章节

### ISIF
- **ISIF = 3**：全松弛（原子位置 + 晶胞形状 + 体积）
- **原因**：块体材料的标准全弛豫设置

### IBRION / POTIM
- **IBRION = 2**：共轭梯度法（CG），最稳健的优化算法
- **POTIM = 0.5**：CG 步长，标准值

### ENCUT
- **ENCUT = 520 eV**
- **原因**：取 POTCAR 中所有元素最大 ENMAX 的 1.3 倍以上，消除晶胞体积变化时的 Pulay 应力
- **参考**：`references/incar_params.md` - 通用参数说明

### KSPACING
- **KSPACING = 0.20**：半导体材料的标准 K 点间距
- **KGAMMA = .TRUE.**：包含 Γ 点，对半导体重要

### 其他参数
- **PREC = Accurate**：标准精度，避免基组截断误差
- **ALGO = Normal**：常规迭代算法，稳定性好
- **EDIFF = 1E-6**：电子步收敛标准，结构松弛时足够
- **EDIFFG = -0.02**：力收敛阈值 0.02 eV/Å
- **NSW = 200**：最大离子步数

## 未进行系统收敛测试

**说明**：本次计算未进行 ENCUT 与 KSPACING 的系统收敛测试（1 meV/atom 标准）。使用模板默认参数，后续如需与文献或 EOS/带隙计算严格对比，建议补充收敛测试。

## 参考来源

1. `references/incar_params.md` - INCAR 参数参考表
2. VASP Wiki: [K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
3. VASP Wiki: [体积松弛与 Pulay 应力消除](https://vasp.at/wiki/Volume_relaxation)
