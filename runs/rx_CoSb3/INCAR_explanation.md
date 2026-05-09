# CoSb3 结构优化 INCAR 参数说明

## 材料分类
- **化学式**：CoSb3（skutterudite 结构）
- **材料类型**：半导体化合物
- **电子结构**：非磁性

## 关键参数选择依据

### 展宽方法（ISMEAR / SIGMA）
- **ISMEAR = 0**（Gaussian 展宽）
  - 原因：CoSb3 是半导体，带隙 > 0.5 eV，使用 Gaussian 展宽避免人工展宽污染价带顶/导带底附近的真实电子态
  - 参考：`references/incar_params.md` 半导体/绝缘体部分

- **SIGMA = 0.05**
  - 原因：小展宽，适合半导体，确保电子态计算精度

### 离子松弛策略（IBRION / ISIF）
- **IBRION = 2**（共轭梯度 CG）
  - 原因：最稳健的算法，适合初始结构优化

- **ISIF = 3**（全松弛）
  - 原因：块体材料标准全弛豫，同时优化原子位置、晶胞形状和体积
  - 参考：`references/incar_params.md` ISIF 选择指南

### 截断能（ENCUT）
- **ENCUT = 520 eV**
  - 原因：取 POTCAR 中最大 ENMAX 的 1.3 倍，消除晶胞体积变化时的 Pulay 应力
  - 参考：VASP 官方体积松弛指南

### 收敛标准
- **EDIFF = 1E-6**：电子步收敛标准
- **EDIFFG = -0.02 eV/Å**：力收敛标准（负值表示力阈值）
- **NSW = 200**：最大离子步数

### K 点网格
- **KSPACING = 0.20 Å⁻¹**
  - 原因：半导体标准设置，INCAR 中设置 KSPACING 后 VASP 自动生成 K 点网格
  - 不生成单独的 KPOINTS 文件

- **KGAMMA = .TRUE.**
  - 原因：确保 Γ 点包含在 K 点网格中

## 计算流程
1. 使用 `setup_vasp_inputs` 生成 POTCAR（KPOINTS 由 INCAR 中的 KSPACING 自动生成）
2. 运行 VASP 结构优化
3. 检查离子步收敛状态（`check_convergence.py`）
4. 若未收敛，将 CONTCAR 复制为 POSCAR 续算
5. 提取最终结果（`analyze_result.py`）

## 注意事项
- 未进行 ENCUT/KSPACING 收敛测试（用户指定跳过）
- 使用模板默认参数，适合大多数半导体化合物
- 若计算过程中出现收敛困难，参考 `references/troubleshooting.md`
