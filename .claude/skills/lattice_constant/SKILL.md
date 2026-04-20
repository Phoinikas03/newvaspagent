---
name: "vasp-lattice-constant-eos"
description: "执行 VASP 平衡晶格常数计算和状态方程 (EOS) 拟合。EOS 前须征得用户同意后，再通过 convergence 做 ENCUT/KSPACING 收敛；否则采用用户指定或模板参数并注明。随后各向同性缩放、批量静态计算、拟合 EOS 得平衡晶格常数与体积。"
version: "1.2.1"
---

# VASP 平衡晶格常数与 EOS 计算工作流 (Lattice Constant & EOS Workflow)

你是一个专业的计算材料学专家。这个 Skill 用于指导你自动化地完成固体材料平衡晶格常数的高精度检索与计算。通过状态方程 (Equation of State, EOS) 拟合能量-体积曲线，是寻找材料基态稳定结构的黄金标准。

## 目录结构

lattice_constant/
├── SKILL.md                       ← 本文件（EOS 工作流）
├── scripts/
│   ├── generate_scaled_poscars.py ← 根据缩放因子列表批量生成带应变的 POSCAR
│   └── fit_eos.py                 ← 提取批量计算能量，拟合 EOS (如 Birch-Murnaghan) 并输出结果 JSON
├── references/
│   ├── convergence_rules.md       ← 占位：指向 convergence/references/convergence_rules.md
│   └── troubleshooting.md         ← EOS 拟合与计算异常
└── templates/
    └── INCAR_static               ← 高精度静态计算 INCAR 模板（填入收敛得到的 ENCUT/KSPACING）

**截断能与 K 点收敛**的完整准则与步骤见独立 skill **`convergence`**（`name`: `vasp-convergence`）。

## 可用工具

- `duckduckgo_search` / `Google Search`：搜索实验晶格常数、空间群信息
- `Skill` (`convergence`)：**ENCUT / KSPACING** 收敛测试（1 meV/atom），产出 **`Convergence_Report.md`**
- `Skill` (`literature`)：检索特定材料的可靠实验晶格常数及标准 EOS 拟合文献
- `get_poscar_from_md`：根据特定材料生成或获取初始 POSCAR
- `setup_vasp_inputs`：生成 POTCAR；若 **INCAR** 含 **`KSPACING`** 则**不**生成 **KPOINTS**
- Skill（`run_vasp`）：按该 skill 与系统 orchestration 规则，用 Bash /（必要时）**非阻塞** `TaskOutput` / 作业调度运行 VASP（MCP 工具 `run_vasp` 已移除，勿再调用）
- `Write` / `Edit`：生成和修改工作区文件
- `Bash`：文件管理、运行预处理与后处理脚本
- `Read` / `Grep`：读取日志和输出文件

**VASP 启动（硬性）**：任何将执行 `mpirun`、直接调用 `vasp_std` / `vasp_gpu` 或等价命令的步骤，**必须先**通过工具调用 **`Skill: run_vasp`** 载入其全文，并按其中「核心执行准则」与用户已确认的 **GPU / CPU** 方案确定 `--np`、`--exe`、`--gpu-per-task`（及 `env_script`）。正式提交时必须**通过** `python .claude/skills/run_vasp/scripts/vasp_runner.py`，**严禁** assistant 直接手写 `mpirun -np 16`（或其它命令）绕过 runner。用户已声明使用 **GPU 版 VASP** 时（可执行文件名仍可能是 `vasp_std`），须遵守 `run_vasp` 中的 **GPU：通常 1 rank ↔ 1 GPU、单卡单任务用 `np=1` 并配合设备绑定**，不得按纯 CPU 逻辑分配 `-np`。

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

### Web / IDE：长计算不冻结界面（流程不变）

本 skill 与前置 **`convergence`** 中的 **`vasp_runner.py`**（可多 `--dirs` **并行**）仍由你**完整编排**：提交、轮询直到结束、再读能量 / 跑 `run_vasp/scripts/check_convergence.py` / `fit_eos.py` 等步骤**一律不少**。

为遵守仓库 **system_prompt** 的 **LOCAL COMPUTE** 规则并避免会话卡死：

1. **启动**：对 **`vasp_runner.py`**（及任何分钟级 VASP 命令）使用 **`Bash` 且 `run_in_background: true`**。单目录单点可显式传 `--log-file`；多 `scale_*` 目录并行时应显式传 `--log-prefix`。
2. **等待完成**：鼓励**周期性检查**而不是高频刷新。对长任务，优先采用较粗的轮询间隔（例如 5 分钟），只在接近结束或需要排障时临时加密。避免用 **`TaskOutput` + `block: true` + 超长 `timeout`**（例如数十万 ms）在**单次工具调用**里一直等到 VASP 结束，因为这会整轮冻结 **Web / IDE**。**应**改用 **`TaskOutput` + `block: false`** 对同一 `task_id` 周期性轮询，直到 `completed` / 失败；若环境不支持非阻塞 `TaskOutput`，则用 Bash 周期性检查各目标目录 `OUTCAR` 是否已有终态能量行、相关 `vasp`/`mpirun` 进程是否仍存活，直至本批任务全部就绪后再进入读结果与收敛检查。
3. 可以使用带 `sleep` 的等待逻辑，但更推荐放在**后台** Bash 或辅助脚本中，以兼顾周期性检查与界面响应性（与 system_prompt 一致）。

上述仅改变**等待方式**，不改变：并行目录集合、每点单独核查、禁止 monolithic `for` 内串行多点 VASP 等规则。

---

## 工作流步骤

### 1. 确认输入与初始结构

1. 确认用户是否提供了目标材料的**元素组成**和**晶体结构类型**（如 FCC, BCC, 金刚石结构）。若未提供，询问用户并等待回复。
2. 检索实验参考值：调用 `Skill: literature` 获取该材料的实验晶格常数。
3. 构建初始结构：调用 `get_poscar_from_md` 或使用脚本，以实验晶格常数为基准生成初始的 `POSCAR`。

---

### 2. 截断能与 K 点收敛（前置：独立 Skill + 用户确认）

**不在本文件中展开细则。** 在载入 **`convergence`** 之前：

1. **询问用户**是否要进行 **ENCUT/KSPACING 收敛测试**（多步静态计算、机时成本；EOS 精度通常依赖合理 **ENCUT/K**），**停止并等待回复**。**禁止**在未获用户同意时自动开始收敛或假定执行。
2. 若用户**同意**，再载入并执行 **`Skill: convergence`**（YAML `name`: `vasp-convergence`；该 skill 内含执行前的用户确认），完成：
   - 静态单点（`NSW=0`）下的 **ENCUT** 与 **`KSPACING`** 扫描；
   - **`Convergence_Report.md`**（含选定 **ENCUT**、**KSPACING** 与能量表）。
3. 若用户**拒绝**或工作区已有可信 **`Convergence_Report.md`**：可**询问**是否**复用**现有报告；否则将用户**指定**或模板中的 **ENCUT/KSPACING** 用于下文，并在说明中注明**未做**或**未重做**系统收敛。

将最终采用的 **ENCUT**、**KSPACING** 填入 **`templates/INCAR_static`** 及所有 **`scale_*`** 子目录的 **INCAR**。

若用户**仅**需要收敛参数、不需要平衡晶格常数，**只执行 `convergence` 即可**，无需继续本 skill 第 3 步及以后。

---

### 3. 生成体积缩放结构 (Volume Scaling)

**目标**：在平衡体积附近生成一系列各向同性缩放的晶胞结构，用于描绘能量势阱。

1. 设定缩放因子列表，通常推荐选取 7-9 个点，例如：`0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06`。
2. `Bash`：`python scripts/generate_scaled_poscars.py --poscar POSCAR --scales 0.94 0.96 0.98 1.00 1.02 1.04 1.06`
3. 检查当前目录下是否已成功生成子文件夹（如 `scale_0.94/`, `scale_0.96/` ...），每个文件夹内包含对应的 `POSCAR`。

---

### 4. 批量静态计算 (Production Runs)

**目标**：获取所有不同体积/缩放比例下系统的精确总能量。

对每个 `scale_x.xx` 子文件夹准备输入并提交计算（各目录可**并行**提交多个独立任务，**禁止**单个脚本在同一进程内 `for` 串行跑完所有 scale）：
1. 复制模板与配置：将 `templates/INCAR_static` 拷贝至当前子目录，并填入 **`convergence`** 得到的 **`ENCUT`** 与 **`KSPACING`**。
2. 调用 `setup_vasp_inputs` 准备与收敛测试一致的 POTCAR；**INCAR** 须含与收敛测试相同的 **`KSPACING`**，以便不生成 **KPOINTS**。
3. 按 Skill `run_vasp` 与 orchestration 规则，**通过 Bash 调用 `python .claude/skills/run_vasp/scripts/vasp_runner.py`**（`run_in_background: true`）及上文 **Web / IDE 等待规则** 在该子目录**单独**提交并完成一次 VASP 计算（一点一任务）；**禁止**长时间阻塞式 `TaskOutput` 冻结会话，也**不得**直接手写 `mpirun ... vasp_std/vasp_gpu`。
4. 该目录计算结束后，`Bash`：`python .claude/skills/run_vasp/scripts/check_convergence.py .`
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

- **收敛测试须用户确认**：载入 **`convergence`** 前**必须**询问用户是否进行；**禁止**自动开始收敛测试。
- **禁止单作业内串行多点 VASP**：除 `generate_scaled_poscars.py`、`fit_eos.py`、`run_vasp/scripts/check_convergence.py` 等明确允许的脚本外，不得用**一个** Bash/Python 脚本或**一次**作业提交，在**同一进程/同一作业**内循环或顺序执行多个 VASP。**允许**将多个单点 VASP 作为多个独立任务**并行**提交；每个任务仍是一点一算、一目录一输入，结束后分别用通用 `check_convergence.py` 等核查。
- **参数绝对一致**：在第 4 步的批量计算中，所有子任务的 `ENCUT`、`POTCAR` 类别和 K 点网格划分方式必须**完全一致**。改变基点截断能会导致 Pulay 应力带来的巨大误差。
- **静态计算优先**：EOS 拟合过程中，各个比例下的 VASP 计算必须是**单点静态计算 (ISIF=2 且 NSW=0)**，不能在内部再次进行晶胞体积松弛，否则能量-体积对应关系将失效。
- **异常点剔除**：若 `fit_eos.py` 报错或拟合曲线存在明显偏离抛物线底部的异常点（例如 SCF 未真正收敛导致的能量畸变），必须重新检查该点的 `OUTCAR`。
- **日志规范**：EOS 目录批量运行时应显式使用 `--log-prefix`，让每个 `scale_*` 子目录中都有稳定、可追溯的运行日志。
