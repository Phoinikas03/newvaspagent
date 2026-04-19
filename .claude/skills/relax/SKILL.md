---
name: "vasp-structure-relaxation"
description: "执行 VASP 结构松弛计算的自动化工作流。当用户要求进行结构松弛、优化晶体结构、或为特定材料准备 VASP 输入文件时触发该技能。"
version: "2.2.0"
---

# VASP 结构松弛计算工作流 (VASP Structure Relaxation Workflow)

你是一个专业的计算材料学专家。这个 Skill 用于指导你自动化地完成 VASP 结构松弛（Structural Relaxation）所需输入文件的准备、计算执行与结果分析。

## 目录结构

```
relax/
├── SKILL.md                          ← 本文件（工作流指令）
├── scripts/
│   ├── check_convergence.py          ← 检查离子步/电子步收敛状态，输出 JSON
│   └── analyze_result.py             ← 提取最终能量、力、压力、体积，输出 JSON
├── references/
│   ├── incar_params.md               ← 按材料类型的 INCAR 参数经验表（含 DFT+U）
│   └── troubleshooting.md            ← 常见报错与处理方案
└── templates/
    ├── INCAR_relax_full              ← ISIF=3 全松弛模板（原子+晶胞）
    └── INCAR_relax_ions              ← ISIF=2 仅松弛原子坐标模板
```

## 可用工具

- `get_poscar_from_md`：根据 Materials Project ID 获取 POSCAR
- `duckduckgo_search` / `google_search`：搜索文档、参数建议、报错解决方案
- `visit_webpage`：提取网页全文
- `Skill` (`literature`)：检索特定材料的 DFT 计算参数文献及实验对比值
- `Skill` (`convergence`)：对**固定 POSCAR** 做静态单点（`NSW=0`）**ENCUT** 与 **`KSPACING`** 收敛测试（1 meV/atom），产出 **`Convergence_Report.md`**。在需要严格确定截断能与 K 点网格、或与后续静态/EOS/带隙计算参数对齐时使用；**不**替代本 skill 中的离子松弛
- `setup_vasp_inputs`：生成 POTCAR 与 POSCAR 拷贝；若 **INCAR** 中含 **`KSPACING`** 则仅用 INCAR 定义 K 点、**不**生成 **KPOINTS**；否则按 `kpoints_density` 生成 **KPOINTS**
- `Write` / `Edit`：生成和修改工作区文件
- `Bash`：文件管理、运行后处理脚本
- `Read` / `Grep`：读取日志和输出文件

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

**执行方式（与系统 ITERATIVE EXECUTION RULE 一致）**：每次 VASP 运行（含 **续算**：`CONTCAR`→`POSCAR` 后的新一轮）须**单独**提交并在继续前检查收敛；**严禁**用 Bash/Python 的 `for` 循环或单条命令把多次松弛/多组 INCAR 试探一次性后台跑完。允许的一次性脚本仅限本 skill `scripts/` 下列出的工具（如 `check_convergence.py`、`analyze_result.py`）。

---

## 工作流步骤

### 1. 获取初始结构

询问用户属于以下哪种情况，等待回复：

- **A. 提供材料名称**：搜索 Materials Project ID，再调用 `get_poscar_from_md` 下载 POSCAR
- **B. 提供 mp-id**：直接调用 `get_poscar_from_md` 下载 POSCAR
- **C. 已有 POSCAR**：请用户提供文件的具体路径

---

### 2. 判断材料类型，确定 INCAR 参数

在写 INCAR 之前，先查阅本地参考文档：

1. `Read references/incar_params.md`，根据材料（金属/半导体/绝缘体/磁性/2D/强关联）确定：
   - `ISMEAR` / `SIGMA`
   - 是否需要 `ISPIN` + `MAGMOM`
   - 是否需要 `LDAU` + `LDAUU`（DFT+U）
   - 是否需要 `IVDW`（vdW 修正）
   - `ISIF` 选择（全优化用 3，固定晶格用 2）

2. 仅当材料特殊（新型钙钛矿、稀土化合物等）且参考文档未覆盖时，调用 `Skill: literature`，并明确告知：
   - **检索目标**：计算参数（需要哪些参数，如 ENCUT、LDAUU、IVDW）
   - **材料体系**：化学式或材料名（如 `"BiFeO3"`）
   - **写入目标**：将返回的引用块追加写入本工作区的 `INCAR_explanation.md`

3. **（可选）ENCUT / KSPACING 收敛**：若希望与文献或后续计算（EOS、带隙、静态能量）**严格可比**的 **ENCUT** 与 **KSPACING**，在写入松弛用 INCAR **之前**，**必须先询问用户**是否要进行 **ENCUT/KSPACING 收敛测试**（说明多步静态计算、耗时与机时），**停止并等待回复**。**不得**在未获用户同意时假定执行或自动载入收敛 skill。若用户**同意**，再载入 **`Skill: convergence`**（该 skill 内含执行前的用户确认流程），对**当前 POSCAR** 做静态单点收敛，将 **`Convergence_Report.md`** 中的参数填入松弛 **INCAR**。若用户**拒绝**或只关心几何优化，使用模板默认 **ENCUT/KSPACING**，并在 **`INCAR_explanation.md`** 中注明未做系统收敛。

---

### 3. 生成 INCAR 与说明文档

1. `Read templates/INCAR_relax_full`（或 `INCAR_relax_ions`，视 ISIF 决定），按材料填入第 2 步确定的参数（模板已含 **`KSPACING`** / **`KGAMMA`**，可按体系收敛需求改 `KSPACING`）
2. `Write INCAR`（写入工作区）
3. `Write INCAR_explanation.md`，记录每个关键参数的选择依据及参考来源

---

### 4. 补全输入文件

调用 `setup_vasp_inputs`，传入 `poscar_path` 和 `incar_path`，自动生成 POTCAR（并在 INCAR 含 **`KSPACING`** 时不生成 **KPOINTS**）。

仅当 **`INCAR` 中未设置 `KSPACING`** 时，才依赖 `kpoints_density` 生成 **KPOINTS**；金属等需更密网格时应**优先**收紧 **`KSPACING`** 数值，而非仅调大 `kpoints_density`。

---

### 5. 运行 VASP 计算

按 Skill `run_vasp`，用 **`Bash` + `run_in_background: true`** 提交计算；等待完成时遵守仓库 **LOCAL COMPUTE**：鼓励**周期性检查**，对长任务优先采用较粗的检查间隔（例如 5 分钟），必要时再临时加密；避免长时间 **`TaskOutput` + `block: true`** 冻结 Web/IDE。优先用 **`block: false`** 的周期性轮询或带 `sleep` 的后台 Bash 检查直至结束，再跑 `check_convergence.py` 等。

---

### 6. 检查收敛状态

计算结束后：

```bash
python scripts/check_convergence.py .
```

根据 JSON 输出判断：

| 字段 | 期望值 | 未达到时的处理 |
|------|--------|--------------|
| `ionic_converged` | `true` | 将 CONTCAR 复制为 POSCAR，增大 NSW 后续算；参考 `references/troubleshooting.md` |
| `nsw_reached` | `false` | 若为 `true` 但 `ionic_converged` 为 `false`，同上续算 |
| `electronic_converged` | `true` | 检查 `errors` 字段，参考 `troubleshooting.md` 调整 ALGO/NELM |
| `contcar_exists` | `true` | 若为 `false`，说明计算异常退出，检查 `errors` 和 `last_lines` |

若遇到报错，**先 `Read references/troubleshooting.md` 查阅处理方案**，未收录的报错再联网搜索。

---

### 7. 提取结果

计算成功后：

```bash
python scripts/analyze_result.py .
```

从 JSON 输出中读取并向用户汇报：
- `final_energy_eV` / `final_energy_per_atom`：最终总能量
- `max_force_eV_A`：最大原子力（应小于 EDIFFG 的绝对值）
- `pressure_kbar`：最终压力（理想松弛结果应接近 0）
- `volume_A3`：最终晶胞体积
- `contcar_path`：松弛后结构文件路径（后续计算的输入）

---

### 8. 结果汇报

向用户报告：
- 松弛是否收敛，最终能量和最大力
- 最终结构文件位置（`CONTCAR`，后续计算应以此为起点）
- 所有关键文件位置：`INCAR`、`INCAR_explanation.md`、`CONTCAR`、`OUTCAR`
- 是否建议进行后续计算（如能带结构计算，可调用 `Skill: bandgap`）

---

## 核心原则

- **禁止 monolithic 循环批量跑 VASP**：不得编写带 `for`/`while` 的 Bash/Python 一次提交多次松弛或多组参数；每次计算或续算均须单独提交并核查后再进行下一步。
- **参数先查本地**：先查 `references/incar_params.md` 和 `troubleshooting.md`；本地未覆盖时调用 `Skill: literature` 检索，而非直接调用 `arxiv_search` 或搜索工具，确保结果结构化且带引用。
- **ENCUT/K 点收敛**：需要生产级 **ENCUT** 与 **KSPACING**（1 meV/atom）时，**须先征得用户同意**再进入 **`convergence`**；该流程为**静态单点**，与离子步松弛分离，完成后将参数并入松弛 **INCAR**。
- **物理严谨性**：时刻关注材料的电子结构分类（金属/半导体、磁性/非磁性），确保 ISMEAR/MAGMOM 等参数设置合理。
- **续算而非重算**：离子步未收敛时，将 CONTCAR 复制为 POSCAR 续算，而不是从头开始。
- **步骤透明**：每完成一个重要节点（获取结构、生成 INCAR、完成收敛检查），向用户简要汇报进度。
