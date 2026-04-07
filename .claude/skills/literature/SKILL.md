---
name: "vasp-lattice-constant-eos"
description: "执行 VASP 平衡晶格常数计算和状态方程 (EOS) 拟合的自动化工作流。采用标准流程：首先进行截断能与 K 点网格的收敛性测试 (1 meV/atom 精度)，随后对晶胞进行多比例各向同性缩放，执行批量静态计算，最后拟合 EOS 曲线以获取理论上最稳定的平衡晶格常数与体积。"
version: "1.2.0"
---

# VASP 平衡晶格常数与 EOS 计算工作流 (Lattice Constant & EOS Workflow)

你是一个专业的计算材料学专家。这个 Skill 用于指导你自动化地完成固体材料平衡晶格常数的高精度检索与计算。通过状态方程 (Equation of State, EOS) 拟合能量-体积曲线，是寻找材料基态稳定结构的黄金标准。

## 技能依赖目录结构 (Skill Assets)

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

## 执行期目录结构规范 (Execution Directory Structure)

在执行计算时，你**必须**在当前 Workspace 中严格构建并维护以下文件树结构。禁止将所有文件混杂在根目录中：

```text
<workspace_root>/
├── POSCAR_mp-<id>                 ← 从 MP 数据库下载的初始结构文件
├── INCAR_production               ← 收敛测试后生成的最终生产用 INCAR (包含最优 ENCUT 和 KSPACING)
├── eos_results.json               ← EOS 拟合后输出的最终结果文件
├── convergence_test/              ← 收敛性测试专属工作目录
│   ├── POSCAR                     ← 用于收敛测试的基础结构文件
│   ├── INCAR_template             ← 测试用的 INCAR 模板
│   ├── encut_test/                ← 截断能测试专属子目录
│   │   └── e_<value>/             ← 例如 e_400/, e_450/
│   └── kspacing_test/             ← K点间距测试专属子目录
│       └── k_<value>/             ← 例如 k_0.30/, k_0.25/
├── scale_0.940/                   ← 体积缩放单点计算子目录 (-6%)
├── scale_0.960/                   ← ...
└── scale_1.060/                   ← 体积缩放单点计算子目录 (+6%)

```

## 可用工具

- `duckduckgo_search` / `Google Search`：搜索实验晶格常数、空间群信息
- `Skill` (`literature`)：检索特定材料的可靠实验晶格常数及标准 EOS 拟合文献
- `get_poscar_from_md`：根据特定材料生成或获取初始 POSCAR
- `setup_vasp_inputs`：自动生成基本输入文件
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
3. 构建初始结构：调用 `get_poscar_from_md` 获取初始结构，该文件应保存在根目录，命名规范为 `POSCAR_mp-<id>`。

---

### 2. 收敛性测试 (Convergence Test)
**目标**：确定满足 1 meV/atom 精度的最优 `ENCUT` 和 `KSPACING`（在 VASP 中，我们优先使用 INCAR 中的 KSPACING 标签，而非显式的 KPOINTS 文件）。

1. **环境准备**：
  - 在根目录创建 `convergence_test/` 文件夹。将 `POSCAR_mp-<id>` 复制到该目录下并重命名为 `POSCAR`。将 `templates/INCAR_static` 复制到该目录命名为 `INCAR_template`。
  - 读取 POTCAR 获取默认的最大截断能 `ENMAX`（使用 `grep ENMAX POTCAR`）。
2. **截断能测试 (ENCUT)**：
  - **固定 K 点**：在 `INCAR` 中固定使用极高密度的 K 点：`KSPACING = 0.10`。
  - **测试范围**：从 `ENMAX` 向上步进 50 eV 取 5-6 个点（例如 `ENMAX`, `ENMAX+50`, `ENMAX+100`...）。
  - **执行**：为每个点创建 `convergence_test/encut_test/e_<value>` 子目录，**确保删除该目录下的 KPOINTS 文件**（以强制 VASP 识别 INCAR 中的 KSPACING），调用计算。
  - **判定**：提取能量，计算相邻步长的差值，选取变化幅度 `< 1 meV/atom` 的最小 `ENCUT`。
3. **K点间距测试 (KSPACING)**：
  - **固定截断能**：在 `INCAR` 中固定使用上一步选出的最优 `ENCUT`。
  - **测试范围**：`KSPACING` 取值依次为：`0.30`, `0.25`, `0.20`, `0.15`, `0.10`（数值越小 K 点越密）。
  - **执行**：为每个点创建 `convergence_test/kspacing_test/k_<value>` 子目录，**务必删除该目录下的 KPOINTS 文件**，调用计算。
  - **判定**：同样以 `< 1 meV/atom` 为标准确定最优的 `KSPACING`。
4. **生成说明文档**：`Write convergence_test/Convergence_Report.md`，记录选定的最优 `ENCUT` 和 `KSPACING`，并列出能量随参数变化的列表。

---

### 3. 生成体积缩放结构 (Volume Scaling)
**目标**：在平衡体积附近生成一系列各向同性缩放的晶胞结构，用于描绘能量势阱。

1. 退回至根目录 `<workspace_root>/` 进行操作。
2. 设定缩放因子列表，例如：`0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06`。
3. 使用 `Bash` 调用脚本：`python scripts/generate_scaled_poscars.py --poscar POSCAR_mp-<id> --scales 0.94 0.96 0.98 1.00 1.02 1.04 1.06`
4. 确认根目录下成功生成了相应的 `scale_x.xxx/` 文件夹。

---

### 4. 批量静态计算 (Production Runs)
**目标**：获取所有不同体积/缩放比例下系统的精确总能量。

1. **生成生产用文件**：在根目录下生成包含收敛参数的 `INCAR_production` (必须包含确定的 `ENCUT` 和 `KSPACING`)。
2. 对于每一个 `scale_x.xxx` 子文件夹，循环执行以下操作：
  - 将根目录的 `INCAR_production` 复制进子目录并重命名为 `INCAR`。
  - 调用 `setup_vasp_inputs` 准备与收敛测试一致的 POTCAR。
  - **关键清理**：执行 `rm -f KPOINTS` 确保子目录内没有 KPOINTS 文件，让 VASP 严格依赖 INCAR 中的 KSPACING。
  - 调用 `run_vasp` 提交计算。
3. 计算结束后，使用 `check_convergence.py` 遍历检查，确认所有 `scale_x.xxx/` 下的 `electronic_converged: true`。

---

### 5. 状态方程拟合 (EOS Fitting)
**目标**：从离散的体积-能量数据点中找出解析能量最低点。

1. 确保所有缩放任务正常结束。
2. 在根目录执行拟合：`Bash`：`python scripts/fit_eos.py --dirs scale_* --eos_type birch_murnaghan > eos_results.json` (或确保脚本直接输出此文件)。
3. 读取 `eos_results.json` 中的结果：
  - `V_0`：平衡体积
  - `E_0`：最低系统能量
  - `B_0`：体积弹性模量 (Bulk Modulus)
  - `a_eq`：计算得出的平衡晶格常数 (Lattice Constant)
  - `R_squared`：拟合优度

---

### 6. 结果汇报与核查
向用户报告：

- 最优计算参数（使用的 ENCUT 和 KSPACING）。
- 计算得出的平衡晶格常数 a_eq 和体积弹性模量 B_0。
- 拟合优度（若 R^2 < 0.99，需警告用户曲线可能未包含能量最低点，需扩大缩放范围）。
- 与实验值的对比：计算误差百分比 `Error (%) = |a_calc - a_exp| / a_exp * 100%`。

---

## 核心原则

- **CRITICAL TOOL USAGE RULE**：在进行参数扫描（如收敛测试或体积缩放批量计算）时，**禁止**编写原生的 Bash/Python 循环脚本直接拉起 `mpirun vasp_std`。你必须在自己的思维链中管理循环逻辑，并逐个目标点调用 `setup_vasp_inputs` 和 `run_vasp` 工具进行任务提交。
- **强制使用 KSPACING**：本工作流废弃了传统的 KPOINTS 文件配置。在执行每次计算前，必须确保目标目录下的 `KPOINTS` 文件被删除，以强迫 VASP 读取 `INCAR` 中的 `KSPACING` 标签。
- **参数绝对一致**：批量计算中，所有的 `ENCUT` 和 `KSPACING` 必须**完全一致**。改变基点截断能会导致 Pulay 应力误差。
- **静态计算优先**：各个比例下的 VASP 计算必须是**单点静态计算 (ISIF=2 且 NSW=0)**，不能在内部再次进行晶胞体积松弛。
- **异常点剔除**：若拟合发散或抛物线异常，必须重新检查对应点的 `OUTCAR`。

---