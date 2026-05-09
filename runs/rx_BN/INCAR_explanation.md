# BN 结构松弛 INCAR 参数说明

## 材料信息
- **化学式**：BN（硼氮化物）
- **晶体类型**：半导体
- **晶胞**：立方晶胞，包含7个B原子和8个N原子

## 关键参数选择依据

### 1. 展宽方法（ISMEAR / SIGMA）
- **ISMEAR = 0**（Gaussian展宽）
- **SIGMA = 0.05**

**理由**：BN是半导体材料（带隙 > 0.5 eV），根据 VASP 官方指南和 `references/incar_params.md`，半导体应使用Gaussian展宽以避免人工展宽污染价带顶/导带底附近的真实电子态。小的SIGMA值（0.05）确保精度。

### 2. 离子松弛策略（IBRION / ISIF）
- **IBRION = 2**（共轭梯度法 CG）
- **ISIF = 3**（全松弛：原子位置 + 晶胞形状 + 体积）

**理由**：
- CG 方法最稳健，适合初始结构的优化
- ISIF=3 用于块体材料的标准全弛豫，同时优化原子坐标和晶胞参数

### 3. 截断能（ENCUT）
- **ENCUT = 520 eV**

**理由**：使用模板默认值。该值通常为POTCAR中最大ENMAX的1.3倍，足以消除Pulay应力（体积变化时的基组截断误差）。

### 4. K点网格（KSPACING / KGAMMA）
- **KSPACING = 0.20 Å⁻¹**
- **KGAMMA = .TRUE.**

**理由**：使用模板默认值。KSPACING=0.20对半导体材料的结构松弛通常足够。KGAMMA=.TRUE.确保Γ点包含在网格中。

**注意**：未进行系统的ENCUT/KSPACING收敛测试（用户选择跳过），参数基于经验模板。若后续需要更高精度（如能带计算），建议使用 `Skill: convergence` 进行收敛测试。

### 5. 收敛标准
- **EDIFF = 1E-6**（电子步收敛）
- **EDIFFG = -0.02 eV/Å**（力收敛）

**理由**：标准的结构松弛精度。力收敛标准-0.02 eV/Å是常用值，确保原子受力足够小。

### 6. 其他参数
- **NSW = 200**：最大离子步数，通常足够
- **POTIM = 0.5**：CG步长，标准值
- **PREC = Accurate**：标准精度
- **ALGO = Normal**：常规迭代算法

## 计算流程
1. 从头开始（ISTART=0）
2. 从叠加原子电荷密度初始化（ICHARG=2）
3. 进行离子松弛，直到力收敛或达到NSW步数
4. 输出最终结构到CONTCAR

## 后续步骤
- 检查收敛状态：`python scripts/check_convergence.py .`
- 提取结果：`python scripts/analyze_result.py .`
- 若未收敛，将CONTCAR复制为POSCAR进行续算

---
**生成时间**：2026-04-18
**工作流**：relax skill
