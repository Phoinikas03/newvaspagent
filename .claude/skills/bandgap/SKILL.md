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
│   ├── gap.py                     ← 从 vasprun.xml 提取带隙，输出 JSON
│   └── check_convergence.py       ← 检查 OUTCAR 收敛状态，输出 JSON
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
- `Skill` (`encut_kspacing_convergence`)：对**固定结构**做 **ENCUT** 与 **`KSPACING`** 收敛（1 meV/atom，`NSW=0`），产出 **`Convergence_Report.md`**。PBE/HSE 共用同一套 **ENCUT** 与 **KSPACING** 前，若尚未收敛，**应优先**通过本 skill 确定参数，再写入 **`INCAR_pbe_scf`** / **`INCAR_hse`**
- `get_poscar_from_md`：根据 Materials Project ID 获取 POSCAR
- `setup_vasp_inputs`：生成 POTCAR 与 POSCAR 拷贝；若 **INCAR** 中含 **`KSPACING`** 则**不**生成 **KPOINTS**
- Skill（`run_vasp`）：按该 skill 与系统 orchestration 规则运行 VASP（MCP 工具 `run_vasp` 已移除）
- `Write` / `Edit`：生成和修改工作区文件
- `Bash`：文件管理、运行后处理脚本
- `Read` / `Grep`：读取日志和输出文件
- `Skill` (`relax`)：引导用户进行结构松弛

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

**执行方式（与系统 ITERATIVE EXECUTION RULE 一致）**：每次 VASP 提交须**单独**执行并在继续前用 `check_convergence.py` 等检查；**严禁**用 Bash/Python 的 `for` 循环或单条命令把 PBE/HSE、多次参数试探或多目录计算一次性后台跑完。PBE 阶段通过并产出有效 `WAVECAR`/`CHGCAR` 后，再进入 HSE；HSE 前须已按步骤向用户确认。允许的一次性脚本仅限本 skill `scripts/` 下列出的后处理（如 `check_convergence.py`、`gap.py`）。

### literature 调用规则（必读）

- **与实验值对比**（实验带隙、实验结构数据等）：**仅当用户明确要求**时再调用 `Skill: literature`（例如用户说「和实验比」「对比文献实验带隙」「查一下实验值」）。若用户只说「整理结果」「汇报结果」「总结带隙」等而未提及实验/文献对比，**只**根据 `gap.py`、本地 `OUTCAR`/`vasprun.xml` 与已有文件汇报，**不得**自动调用 `literature`，也不得自动 `arxiv_search` / `google_search` 做实验对比。
- **HSE 计算参数**（`HFSCREEN`、`AEXX` 等）：优先 `Read references/hse_params.md`。若材料特殊且本地未覆盖，**先询问用户**是否需要通过 `literature` 检索参数；**不得**在未获同意时自动调用。

---

## 工作流步骤

### 1. 确认输入与结构状态

询问用户是否已有松弛好的 `CONTCAR` 或 `POSCAR` 文件，以及文件的具体路径，等待回复。

若用户只有未优化的初始结构，建议先调用 `Skill`（`relax`）执行结构松弛。

**与 `encut_kspacing_convergence` 的配合**：带隙计算依赖可靠的 **ENCUT** 与 **KSPACING**。若当前工作区**尚无**针对该松弛后结构的 **`Convergence_Report.md`**（或需重新收敛），在进入下方 **§3 PBE** 之前，**必须先询问用户**是否要进行 **ENCUT/KSPACING 收敛测试**（说明多步静态计算与机时），**停止并等待回复**。**不得**在未获用户同意时自动开始收敛。若用户**同意**，再载入 **`Skill: encut_kspacing_convergence`**（内含执行前确认），以**最终用于 PBE 的 POSCAR** 做静态收敛，再将 **ENCUT**、**KSPACING** 用于 PBE 与 HSE（两阶段必须一致）。若用户**拒绝**或仅做探索性计算，使用模板/初值 **ENCUT/KSPACING**，并在 **`HSE_INCAR_explanation.md`**（或等价说明）中注明未做系统收敛。

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

1. `Read templates/INCAR_pbe_scf`，按材料调整 **`ENCUT`** 与 **`KSPACING`**：优先采用 **`encut_kspacing_convergence`** 给出的收敛值；若无报告，可用 POTCAR 中最大 ENMAX × 1.3 作为 **ENCUT** 初值、模板 **KSPACING**，并在文档中说明未做系统收敛。**`KSPACING`**（及 **`KGAMMA`**）在 PBE 与后续 HSE 中必须一致
2. `Write INCAR`（覆写）
3. `Bash`：`cp INCAR INCAR_pbe`（保留历史版本，不可省略）
4. 调用 `setup_vasp_inputs` 准备 POTCAR（含 **`KSPACING`** 时不生成 **KPOINTS**）
5. 按 Skill `run_vasp`，用 Bash 或 `TaskOutput` 提交 PBE 步 VASP 计算
6. 计算结束后，`Bash`：`python scripts/check_convergence.py .`
   - 确认 `electronic_converged: true`
   - 确认 `wavecar_nonempty: true` 且 `chgcar_nonempty: true`
   - 若未收敛，读取 `errors` 和 `last_lines` 字段，参考 `references/troubleshooting.md` 排查，修正 INCAR 后重试

---

### 4. 第二阶段：HSE06 高精度计算

**目标**：基于 PBE 波函数热启动，获得准确带隙。

1. 确认工作区内 `WAVECAR` 和 `CHGCAR` 均存在且非空（来自第 3 步）
2. `Read templates/INCAR_hse`，将 `ENCUT`、**`KSPACING`**（及 **`KGAMMA`**）设为与 PBE SCF **完全一致**，填入第 2 步确定的 HSE 参数
3. `Write INCAR`（覆写）
4. `Bash`：`cp INCAR INCAR_hse`（保留历史版本，不可省略）
5. 生成说明文档：`Write HSE_INCAR_explanation.md`，记录 PBE→HSE 的参数逻辑及参考来源
6. 向用户确认是否继续（HSE 耗时极长），等待回复后再按 Skill `run_vasp` 运行 HSE 步
7. 计算结束后，`Bash`：`python scripts/check_convergence.py .`
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
- **ENCUT / KSPACING 收敛**：正式带隙对比或发表级计算前，宜对松弛后结构做收敛；**须先征得用户同意**再载入 **`encut_kspacing_convergence`**，再贯穿 PBE 与 HSE；若用户选择不做，须在说明文档中声明风险。
- **历史文件追溯**：`INCAR_pbe` 和 `INCAR_hse` 必须在工作区中同时存在，不允许静默覆盖。
- **参数先查本地**：先查 `references/hse_params.md` 和 `references/troubleshooting.md`。本地未覆盖且**用户同意**用文献补 HSE 参数时，再按 §2 调用 `Skill: literature`。**实验带隙对比**仅在用户明确要求时调用 literature（见上文 **literature 调用规则**）；不得用 `arxiv_search` / `google_search` 替代用户未请求的实验对比。
