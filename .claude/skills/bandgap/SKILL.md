---
name: "vasp-band-structure-hse"
description: "执行 VASP 能带结构和高精度带隙计算的自动化工作流。采用两步法：首先进行常规 PBE 计算获取电荷与波函数信息，随后重启进行高精度 HSE (杂化泛函) 计算，并自动提取带隙。当用户要求计算能带、带隙 (Band Gap) 或指定进行 HSE 计算时触发该技能。"
version: "2.0.0"
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
- `Skill` (`literature`)：检索特定材料的 HSE 计算参数文献及实验带隙对比值
- `get_poscar_from_md`：根据 Materials Project ID 获取 POSCAR
- `setup_vasp_inputs`：自动生成 KPOINTS、POTCAR
- `run_vasp`：执行 VASP 计算（禁止直接在 Bash 中运行 VASP）
- `Write` / `Edit`：生成和修改工作区文件
- `Bash`：文件管理、运行后处理脚本
- `Read` / `Grep`：读取日志和输出文件
- `Skill` (`relax`)：引导用户进行结构松弛

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

---

## 工作流步骤

### 1. 确认输入与结构状态

询问用户是否已有松弛好的 `CONTCAR` 或 `POSCAR` 文件，以及文件的具体路径，等待回复。

若用户只有未优化的初始结构，建议先调用 `Skill`（`relax`）执行结构松弛。

---

### 2. 确定 HSE 参数

在写 INCAR 之前，先查阅本地参考文档：
- `Read references/hse_params.md`，根据材料类型确认 `HFSCREEN`、`AEXX`、`ALGO` 等参数。
- 仅当材料特殊（如强关联、新型钙钛矿等）且参考文档未覆盖时，调用 `Skill: literature`，并明确告知：
  - **检索目标**：计算参数（HFSCREEN、AEXX、ALGO 等 HSE 参数）
  - **材料体系**：化学式或材料名（如 `"BiFeO3"`）
  - **写入目标**：将返回的引用块追加写入本工作区的 `HSE_INCAR_explanation.md`

---

### 3. 第一阶段：PBE 静态自洽计算

**目标**：获得高质量波函数（`WAVECAR`）和电荷密度（`CHGCAR`），供 HSE 续算使用。

1. `Read templates/INCAR_pbe_scf`，按材料调整 `ENCUT`（取 POTCAR 中最大 ENMAX × 1.3）
2. `Write INCAR`（覆写）
3. `Bash`：`cp INCAR INCAR_pbe`（保留历史版本，不可省略）
4. 调用 `setup_vasp_inputs` 准备 POTCAR 和 KPOINTS
5. 调用 `run_vasp` 提交计算
6. 计算结束后，`Bash`：`python scripts/check_convergence.py .`
   - 确认 `electronic_converged: true`
   - 确认 `wavecar_nonempty: true` 且 `chgcar_nonempty: true`
   - 若未收敛，读取 `errors` 和 `last_lines` 字段，参考 `references/troubleshooting.md` 排查，修正 INCAR 后重试

---

### 4. 第二阶段：HSE06 高精度计算

**目标**：基于 PBE 波函数热启动，获得准确带隙。

1. 确认工作区内 `WAVECAR` 和 `CHGCAR` 均存在且非空（来自第 3 步）
2. `Read templates/INCAR_hse`，将 `ENCUT` 设为与 PBE SCF **完全一致**的值，填入第 2 步确定的 HSE 参数
3. `Write INCAR`（覆写）
4. `Bash`：`cp INCAR INCAR_hse`（保留历史版本，不可省略）
5. 生成说明文档：`Write HSE_INCAR_explanation.md`，记录 PBE→HSE 的参数逻辑及参考来源
6. 向用户确认是否继续（HSE 耗时极长），等待回复后再调用 `run_vasp`
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

向用户报告：
- HSE06 带隙值（eV）及带隙类型（直接/间接）
- 跃迁路径
- 与实验值的对比：调用 `Skill: literature`，并明确告知：
  - **检索目标**：实验对比值（带隙实验测量值）
  - **材料体系**：当前计算材料的化学式
  - **写入目标**：将返回的引用块（含实验值对比表）追加写入 `HSE_INCAR_explanation.md`
- 所有关键文件的最终位置：`INCAR_pbe`、`INCAR_hse`、`HSE_INCAR_explanation.md`、`vasprun.xml`、`OUTCAR`

---

### 7. 反思与质检

- 读取 `vasprun.xml`，核查带隙信息是否与 `gap.py` 输出一致
- 检查 OUTCAR 末尾是否已运行到最大步数（可能需要续算）
- 若带隙为 0 但材料已知是半导体，参考 `references/troubleshooting.md` 中"带隙为 0"排查步骤

---

## 核心原则

- **WAVECAR 连续性**：`ISTART=1` 是 HSE 阶段热启动的关键，绝不能在 HSE 阶段设 `ISTART=0`。
- **ENCUT 一致性**：PBE 和 HSE 两阶段的 `ENCUT` 必须完全相同，否则 WAVECAR 无法读取。
- **历史文件追溯**：`INCAR_pbe` 和 `INCAR_hse` 必须在工作区中同时存在，不允许静默覆盖。
- **参数先查本地**：先查 `references/hse_params.md` 和 `references/troubleshooting.md`；本地未覆盖时调用 `Skill: literature` 检索，而非直接调用 `arxiv_search` 或搜索工具，确保结果结构化且带引用。
