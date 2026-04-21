---
name: "vasp-band-structure-hse"
description: "执行 VASP 能带结构和高精度带隙计算的自动化工作流。采用两步法：首先进行常规 PBE 计算获取电荷与波函数信息，随后重启进行高精度 HSE (杂化泛函) 计算，并自动提取带隙。当用户要求计算能带、带隙 (Band Gap) 或指定进行 HSE 计算时触发该技能。"
version: "2.2.1"
---

# VASP 能带结构计算工作流 (VASP Band Structure & HSE Workflow)

你是一个专业的计算材料学专家。这个 Skill 用于指导你自动化地完成 VASP 能带结构和带隙的高精度计算。HSE06 计算成本极高，因此严格采用"PBE 预计算 → HSE 续算"的两步法策略。

## 目录结构

```
bandgap/
├── SKILL.md                       ← 本文件（工作流指令）
├── scripts/
│   └── gap.py                     ← 从 vasprun.xml 提取带隙，输出 JSON
├── references/
│   ├── hse_params.md              ← 不同材料体系的 HSE 参数经验值
│   └── troubleshooting.md         ← 常见报错与处理方案
└── templates/
    ├── INCAR_pbe_scf              ← PBE 静态计算 INCAR 模板
    └── INCAR_hse                  ← HSE06 计算 INCAR 模板
```

## 可用工具

- `duckduckgo_search` / `google_search`：搜索文档、论坛、参数建议
- `visit_webpage`：提取网页全文
- `Skill` (`literature`)：仅在**用户明确要求**时用于检索（见下文 **literature 调用规则**）
- `Skill` (`convergence`)：对**固定结构**做 **ENCUT** 与 **`KSPACING`** 收敛（1 meV/atom，`NSW=0`），产出 **`Convergence_Report.md`**。PBE/HSE 共用同一套 **ENCUT** 与 **KSPACING** 前，若尚未收敛，**应优先**通过本 skill 确定参数，再写入 **`INCAR_pbe_scf`** / **`INCAR_hse`**
- `get_poscar_from_md`：根据 Materials Project ID 获取 POSCAR
- `setup_vasp_inputs`：生成 POTCAR 与 POSCAR 拷贝；若 **INCAR** 中含 **`KSPACING`** 则**不**生成 **KPOINTS**
- Skill（`run_vasp`）：按该 skill 与系统 orchestration 规则运行 VASP（MCP 工具 `run_vasp` 已移除）
- Skill（`performance`）：当用户提到 GPU、`KPAR`、`NCORE`、`NPAR`、并行数量，或需要按硬件决定并行策略时，必须先用该 skill 确定并行参数，再写最终 `INCAR`
- `Write` / `Edit`：生成和修改工作区文件
- `Bash`：文件管理、运行后处理脚本
- `Read` / `Grep`：读取日志和输出文件
- `Skill` (`relax`)：引导用户进行结构松弛

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

**执行方式（与系统 ITERATIVE EXECUTION RULE 一致）**：每次 VASP 提交须**单独**执行并在继续前用 `run_vasp/scripts/check_convergence.py` 等检查；**严禁**用 Bash/Python 的 `for` 循环或单条命令把 PBE/HSE、多次参数试探或多目录计算一次性后台跑完。PBE 阶段通过并产出有效 `WAVECAR`/`CHGCAR` 后，再进入 HSE；HSE 前须已按步骤向用户确认。允许的一次性脚本仅限本 skill `scripts/` 与 `run_vasp/scripts/` 下列出的后处理（如 `gap.py`、`check_convergence.py`）。

**HSE 启动前确认（强制）**：
- 在 **PBE 已收敛**、且 **HSE 输入文件已准备完成** 后，必须**单独输出一条面向用户的纯文本确认消息**，明确说明 HSE 计算即将开始、成本高、预计更耗时，并**停止生成，等待用户回复**。
- **禁止**在同一轮里一边说“现在启动 HSE”一边直接调用 Bash / `run_vasp` / `TaskOutput` 启动 HSE。也就是说：**询问** 与 **实际启动 HSE** 必须分成两个独立回合。
- 若检测到可用 GPU，必须在该确认消息中明确告知：**HSE 可选择使用 1 卡或多卡 GPU**，并**明确询问用户希望使用多少张 GPU**。
- 在用户尚未明确回复“继续”以及未明确给出 **GPU 卡数**（如 `1`、`2`、`4` 等）之前，**不得**提交 HSE 任务。
- 若用户只回复“继续”但未说明 GPU 卡数，而当前环境存在 GPU，必须继续追问 GPU 数量；**不得**自行默认 1 卡或多卡。
- 只要用户已提到 GPU、`KPAR`、`NCORE`、`NPAR` 或“并行怎么设”，就不得直接沿用模板中的旧并行参数；必须先调用 `Skill: performance`，根据硬件场景生成或修改最终并行设置。

### literature 调用规则（必读）

- **与实验值对比**（实验带隙、实验结构数据等）：**仅当用户明确要求**时再调用 `Skill: literature`（例如用户说「和实验比」「对比文献实验带隙」「查一下实验值」）。若用户只说「整理结果」「汇报结果」「总结带隙」等而未提及实验/文献对比，**只**根据 `gap.py`、本地 `OUTCAR`/`vasprun.xml` 与已有文件汇报，**不得**自动调用 `literature`，也不得自动 `arxiv_search` / `google_search` 做实验对比。
- **HSE 计算参数**（`HFSCREEN`、`AEXX` 等）：优先 `Read references/hse_params.md`。若材料特殊且本地未覆盖，**先询问用户**是否需要通过 `literature` 检索参数；**不得**在未获同意时自动调用。

---

## 工作流步骤

### 1. 确认输入与结构状态

询问用户是否已有松弛好的 `CONTCAR` 或 `POSCAR` 文件，以及文件的具体路径，等待回复。

若用户只有未优化的初始结构，建议先调用 `Skill`（`relax`）执行结构松弛。

**与 `convergence` 的配合**：带隙计算依赖可靠的 **ENCUT** 与 **KSPACING**。若当前工作区**尚无**针对该松弛后结构的 **`Convergence_Report.md`**（或需重新收敛），在进入下方 **§3 PBE** 之前，**必须先询问用户**是否要进行 **ENCUT/KSPACING 收敛测试**（说明多步静态计算与机时），**停止并等待回复**。**不得**在未获用户同意时自动开始收敛。若用户**同意**，再载入 **`Skill: convergence`**（内含执行前确认），以**最终用于 PBE 的 POSCAR** 做静态收敛，再将 **ENCUT**、**KSPACING** 用于 PBE 与 HSE（两阶段必须一致）。若用户**拒绝**或仅做探索性计算，使用模板/初值 **ENCUT/KSPACING**，并在 **`HSE_INCAR_explanation.md`**（或等价说明）中注明未做系统收敛。

---

### 2. 确定 HSE 参数

在写 INCAR 之前，先查阅本地参考文档：
- `Read references/hse_params.md`，根据材料类型确认 `HFSCREEN`、`AEXX`、`ALGO` 等参数。
- 仅当材料特殊（如强关联、新型钙钛矿等）且参考文档未覆盖时，**先询问用户**是否同意通过 `Skill: literature` 检索计算参数；若用户同意，再调用，并明确告知：
  - **检索目标**：计算参数（HFSCREEN、AEXX、ALGO 等 HSE 参数）
  - **材料体系**：化学式或材料名（如 `"BiFeO3"`）
  - **写入目标**：将返回的引用块追加写入本工作区的 `HSE_INCAR_explanation.md`

---

### 3. 第一阶段：PBE 静态自洽计算

**目标**：获得高质量波函数（`WAVECAR`）和电荷密度（`CHGCAR`），供 HSE 续算使用。

1. `Read templates/INCAR_pbe_scf`，按材料调整 **`ENCUT`** 与 **`KSPACING`**：优先采用 **`convergence`** 给出的收敛值；若无报告，可用 POTCAR 中最大 ENMAX × 1.3 作为 **`ENCUT`** 初值、模板 **`KSPACING`**，并在文档中说明未做系统收敛。**`KSPACING`**（及 **`KGAMMA`**）在 PBE 与后续 HSE 中必须一致
2. 若用户已经说明使用 GPU，或明确提到 `KPAR` / `NCORE` / `NPAR` / 并行数量，必须先调用 `Skill: performance`，结合当前硬件为 PBE 阶段确定并行参数；不要自行拍脑袋保留或写入默认并行项
3. `Write INCAR`（覆写）
4. `Bash`：`cp INCAR INCAR_pbe`（保留历史版本，不可省略）
5. 调用 `setup_vasp_inputs` 准备 POTCAR（含 **`KSPACING`** 时不生成 **KPOINTS**）
6. 按 Skill `run_vasp`，**通过 Bash 调用 `python .claude/skills/run_vasp/scripts/vasp_runner.py`** 提交 PBE 步 VASP 计算；**不得**直接手写 `mpirun ... vasp_std/vasp_gpu`。单目录时应显式传 `--log-file vasp_pbe.log`
7. 计算结束后，`Bash`：`python .claude/skills/run_vasp/scripts/check_convergence.py .`
   - 确认 `electronic_converged: true`
   - 确认 `wavecar_nonempty: true` 且 `chgcar_nonempty: true`
   - 若未收敛，读取 `errors` 和 `last_lines` 字段，参考 `references/troubleshooting.md` 排查，修正 INCAR 后重试

---

### 4. 第二阶段：HSE06 高精度计算

**目标**：基于 PBE 波函数热启动，获得准确带隙。

1. 确认工作区内 `WAVECAR` 和 `CHGCAR` 均存在且非空（来自第 3 步）
2. `Read templates/INCAR_hse`，将 `ENCUT`、**`KSPACING`**（及 **`KGAMMA`**）设为与 PBE SCF **完全一致**，填入第 2 步确定的 HSE 参数
3. 若用户已经说明使用 GPU，或明确提到 `KPAR` / `NCORE` / `NPAR` / 并行数量，必须在写 HSE `INCAR` 之前先调用 `Skill: performance`，由该 skill 根据单 GPU、多 GPU、CPU-only 或多节点场景确定并行项；不要沿用模板默认值，也不要只改启动命令而不改 `INCAR`
4. `Write INCAR`（覆写）
5. `Bash`：`cp INCAR INCAR_hse`（保留历史版本，不可省略）
6. 生成说明文档：`Write HSE_INCAR_explanation.md`，记录 PBE→HSE 的参数逻辑及参考来源
7. **单独**向用户确认是否继续（HSE 耗时极长），等待回复后再按 Skill `run_vasp` **通过 `vasp_runner.py`** 运行 HSE 步；**不得**直接手写 `mpirun ... vasp_std/vasp_gpu`。单目录时应显式传 `--log-file vasp_hse.log`
   - 若检测到 GPU，可明确告诉用户：HSE 可使用 **1 卡或多卡 GPU**
   - 必须**明确询问 GPU 数量**
   - 该轮只允许询问并等待回复，**不得**在同一轮直接启动 HSE
   - 若 HSE 因 GPU 报错需要调整卡数或避开坏卡，仍必须回到 `run_vasp` 的流程：先核实旧 HSE 进程是否还活着；若仍在，定点终止已确认属于当前目录的旧进程树并等待其退出；然后再用 **`vasp_runner.py`** 重新提交。**禁止**直接在同一 `hse_scf` 目录里手写 `mpirun ... &` 补开第二个 HSE 进程
8. 计算结束后，`Bash`：`python .claude/skills/run_vasp/scripts/check_convergence.py .`
   - 若遇到报错，先 `Read references/troubleshooting.md` 查阅处理方案
   - `ZBRENT: fatal error` 等已知报错在 `vasprun.xml` 完整生成的前提下可安全忽略

---

### 5. 后处理：提取带隙

1. 确认 `vasprun.xml` 的确切路径
2. `Bash`：`python scripts/gap.py <vasprun.xml路径>`
3. 从 JSON 输出中读取：
   - `energy_eV`：带隙值（eV）
   - `direct`：是否为直接带隙
   - `transition`：带隙跃迁路径（如 `Γ→X`）

---

### 6. 结果汇报

向用户报告（**默认必备**，不依赖 literature）：
- HSE06 带隙值（eV）及带隙类型（直接/间接）
- 跃迁路径
- 所有关键文件的最终位置：`INCAR_pbe`、`INCAR_hse`、`HSE_INCAR_explanation.md`（若已生成）、`vasprun.xml`、`OUTCAR`

**与实验值的对比（可选）**：**仅当用户明确要求**对比实验带隙或实验数据时，再调用 `Skill: literature`，并明确告知：
  - **检索目标**：实验对比值（带隙实验测量值等）
  - **材料体系**：当前计算材料的化学式
  - **写入目标**：将返回的引用块（含实验值对比表）追加写入 `HSE_INCAR_explanation.md`（若用户需要落盘）

用户未要求实验对比时，**禁止**为「丰富报告」而自动调用 `literature` 或网页搜索。

---

### 7. 反思与质检

- 读取 `vasprun.xml`，核查带隙信息是否与 `gap.py` 输出一致
- 检查 OUTCAR 末尾是否已运行到最大步数（可能需要续算）
- 若带隙为 0 但材料已知是半导体，参考 `references/troubleshooting.md` 中"带隙为 0"排查步骤

---

## 核心原则

- **禁止 monolithic 循环批量跑 VASP**：不得编写带 `for`/`while` 的 Bash/Python 一次提交多阶段或多组 INCAR 的 VASP；须逐次提交并逐步核查（与本 skill 第 3、4 步顺序一致）。
- **WAVECAR 连续性**：`ISTART=1` 是 HSE 阶段热启动的关键，绝不能在 HSE 阶段设 `ISTART=0`。
- **ENCUT 一致性**：PBE 和 HSE 两阶段的 `ENCUT` 必须完全相同，否则 WAVECAR 无法读取。
- **ENCUT / KSPACING 收敛**：正式带隙对比或发表级计算前，宜对松弛后结构做收敛；**须先征得用户同意**再载入 **`convergence`**，再贯穿 PBE 与 HSE；若用户选择不做，须在说明文档中声明风险。
- **HSE 前单独确认**：HSE 启动前必须有一个**独立用户回合**用于确认是否继续；若有 GPU，还必须明确问清 **GPU 卡数**。在未获得这些确认前，禁止提交 HSE。
- **并行参数先交给 performance**：一旦用户提到 GPU、`KPAR`、`NCORE`、`NPAR` 或要求按硬件优化，PBE/HSE 两阶段都必须先调用 **`Skill: performance`** 再写最终 `INCAR`；`bandgap` 模板不得私自保留默认 `NCORE`。
- **GPU 报错后的重启**：若 PBE/HSE 因 GPU 故障改用新卡数或新 GPU 布局重试，必须先确认旧运行已退出或已被定点清理；不得让两个活跃的 VASP 进程同时占用同一 `pbe_scf` / `hse_scf` 目录，也不得让两个活跃进程同时写同一个 `vasp_*.log`。
- **历史文件追溯**：`INCAR_pbe` 和 `INCAR_hse` 必须在工作区中同时存在，不允许静默覆盖。
- **参数先查本地**：先查 `references/hse_params.md` 和 `references/troubleshooting.md`。本地未覆盖且**用户同意**用文献补 HSE 参数时，再按 §2 调用 `Skill: literature`。**实验带隙对比**仅在用户明确要求时调用 literature（见上文 **literature 调用规则**）；不得用 `arxiv_search` / `google_search` 替代用户未请求的实验对比。
