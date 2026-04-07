---
name: "vasp-lattice-constant-eos"
description: "执行 VASP 平衡晶格常数计算和状态方程 (EOS) 拟合的自动化工作流。采用标准流程：首先进行截断能与 K 点网格的收敛性测试 (1 meV/atom 精度)，随后对晶胞进行多比例各向同性缩放，执行批量静态计算，最后拟合 EOS 曲线以获取理论上最稳定的平衡晶格常数与体积。"
version: "1.0.0"
---

# VASP 平衡晶格常数与 EOS 计算工作流 (Lattice Constant & EOS Workflow)

你是一个专业的计算材料学专家。这个 Skill 用于指导你自动化地完成固体材料平衡晶格常数的高精度检索与计算。通过状态方程 (Equation of State, EOS) 拟合能量-体积曲线，是寻找材料基态稳定结构的黄金标准。

## 目录结构

lattice_eos/
├── SKILL.md                       ← 本文件（工作流指令）
├── scripts/
│   ├── generate_scaled_poscars.py ← 根据缩放因子列表批量生成带应变的 POSCAR
│   ├── fit_eos.py                 ← 提取批量计算能量，拟合 EOS (如 Birch-Murnaghan) 并输出结果 JSON
│   └── check_convergence.py       ← 检查单次 VASP 计算 OUTCAR 收敛状态
├── references/
│   ├── convergence_rules.md       ← 截断能与 K 点收敛标准的经验准则
│   └── troubleshooting.md         ← 常见报错与物理意义异常（如拟合发散）处理方案
└── templates/
    └── INCAR_static               ← 高精度静态计算 INCAR 模板

## 可用工具

- `duckduckgo_search` / `Google Search`：搜索实验晶格常数、空间群信息
- `Skill` (`literature`)：检索特定材料的可靠实验晶格常数及标准 EOS 拟合文献
- `get_poscar_from_md`：根据特定材料生成或获取初始 POSCAR
- `setup_vasp_inputs`：自动生成 KPOINTS、POTCAR
- `run_vasp`：执行 VASP 计算（禁止直接在 Bash 中运行 VASP）
- `Write` / `Edit`：生成和修改工作区文件
- `Bash`：文件管理、运行预处理与后处理脚本
- `Read` / `Grep`：读取日志和输出文件

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

---

## 工作流步骤

### 1. 确认输入与初始结构

1. 确认用户是否提供了目标材料的**元素组成**和**晶体结构类型**（如 FCC, BCC, 金刚石结构）。若未提供，询问用户并等待回复。
2. 检索实验参考值：调用 `Skill: literature` 获取该材料的实验晶格常数。
3. 构建初始结构：调用 `get_poscar_from_md` 或使用脚本，以实验晶格常数为基准生成初始的 `POSCAR`。

---

### 2. 收敛性测试 (Convergence Test)

**目标**：确定满足 1 meV/atom 精度的最优 `ENCUT` 和 K 点网格 (`KPOINTS`)。

1. `Read references/convergence_rules.md` 获取默认测试范围。
2. **截断能测试**：固定高密度 K 点，逐步提升 `ENCUT` 运行单点能计算。提取每步总能量，计算相邻两步的能量差值。
3. **K点测试**：固定刚刚找到的最优 `ENCUT`，逐步增加 K 点密度运行单点能计算。
4. **判定标准**：当能量变化低于 1 meV/atom 时，将此时的 `ENCUT` 和 K 点密度作为后续生产计算的固定参数。
5. 生成说明文档：`Write Convergence_Report.md`，记录选定的最优参数及收敛数据。

---

### 3. 生成体积缩放结构 (Volume Scaling)

**目标**：在平衡体积附近生成一系列各向同性缩放的晶胞结构，用于描绘能量势阱。

1. 设定缩放因子列表，通常推荐选取 7-9 个点，例如：`0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06`。
2. `Bash`：`python scripts/generate_scaled_poscars.py --poscar POSCAR --scales 0.94 0.96 0.98 1.00 1.02 1.04 1.06`
3. 检查当前目录下是否已成功生成子文件夹（如 `scale_0.94/`, `scale_0.96/` ...），每个文件夹内包含对应的 `POSCAR`。

---

### 4. 批量静态计算 (Production Runs)

**目标**：获取所有不同体积/缩放比例下系统的精确总能量。

对于每一个 `scale_x.xx` 子文件夹，循环执行以下操作：
1. 复制模板与配置：将 `templates/INCAR_static` 拷贝至当前子目录，并填入第 2 步确定的最优 `ENCUT`。
2. 调用 `setup_vasp_inputs` 准备与收敛测试一致的 POTCAR 和 KPOINTS。
3. 调用 `run_vasp` 提交计算。
4. 计算结束后，`Bash`：`python scripts/check_convergence.py .`
   - 确认 `electronic_converged: true`。
   - 若未收敛，查阅 `references/troubleshooting.md`，可能需要增加 `NELM` 或调整 `ALGO` 算法后重试该点。

---

### 5. 状态方程拟合 (EOS Fitting)

**目标**：从离散的体积-能量数据点中找出解析能量最低点。

1. 确保所有缩放任务的 VASP 计算均正常结束。
2. `Bash`：`python scripts/fit_eos.py --dirs scale_* --eos_type birch_murnaghan`
3. 从脚本输出的 JSON 中读取结果：
   - `V_0`：平衡体积
   - `E_0`：最低系统能量
   - `B_0`：体积弹性模量 (Bulk Modulus)
   - `a_eq`：计算得出的平衡晶格常数 (Lattice Constant)
   - `R_squared`：拟合优度

---

### 6. 结果汇报与核查

向用户报告：
- 最优计算参数（使用的 ENCUT 和 K 点网格）。
- 计算得出的平衡晶格常数 a_eq 和体积弹性模量 B_0。
- 拟合优度（若 R^2 < 0.99，需警告用户曲线可能未包含能量最低点，需扩大缩放范围）。
- 与实验值的对比：将计算结果与第 1 步检索到的实验晶格常数进行对比，计算误差百分比 `Error (%) = |a_calc - a_exp| / a_exp * 100%`。

---

## 核心原则

- **参数绝对一致**：在第 4 步的批量计算中，所有子任务的 `ENCUT`、`POTCAR` 类别和 K 点网格划分方式必须**完全一致**。改变基点截断能会导致 Pulay 应力带来的巨大误差。
- **静态计算优先**：EOS 拟合过程中，各个比例下的 VASP 计算必须是**单点静态计算 (ISIF=2 且 NSW=0)**，不能在内部再次进行晶胞体积松弛，否则能量-体积对应关系将失效。
- **异常点剔除**：若 `fit_eos.py` 报错或拟合曲线存在明显偏离抛物线底部的异常点（例如 SCF 未真正收敛导致的能量畸变），必须重新检查该点的 `OUTCAR`。