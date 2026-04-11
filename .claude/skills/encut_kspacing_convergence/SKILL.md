---
name: "vasp-encut-kspacing-convergence"
description: "对固定几何的单胞执行 VASP 静态单点能（NSW=0）下的截断能 ENCUT 与 INCAR 中 KSPACING 收敛测试，目标相邻步能量差 ≤1 meV/atom，输出 Convergence_Report.md 与推荐生产参数。适用于 EOS、带隙扫描、一般静态能量对比等任意需要先收敛 ENCUT/K 点的前置步骤。"
version: "1.1.0"
---

# VASP 截断能与 K 点收敛（ENCUT & KSPACING Convergence）

你是一个专业的计算材料学专家。本 Skill 把 **ENCUT** 与 **`KSPACING`**（INCAR 自动 K 点，**不写 KPOINTS 文件**）的收敛测试抽成独立流程，供 `lattice_constant`、文献工作流或其它需要 **静态单点能** 精度保证的任务复用。

## 目录结构

```
encut_kspacing_convergence/
├── SKILL.md                          ← 本文件
├── references/
│   └── convergence_rules.md          ← 扫描序列、1 meV/atom 判据、注意事项
├── scripts/
│   └── check_convergence.py          ← 单次计算后检查 OUTCAR 电子步是否收敛
└── templates/
    └── INCAR_static_convergence      ← 静态单点 INCAR 模板（复制后改参数）
```

## 适用计算类型

- **必须**：固定晶胞与原子位置（**`NSW = 0`**），仅比较**总能量**以判断收敛。
- **典型**：EOS 前的参数准备、带隙/能带前的静态基准、一般能量差对比。
- **不适用**：需要同时松弛离子/晶胞时，应先在 `relax` 等 skill 中完成结构优化，再对**最终结构**做本收敛测试。

## 可用工具

- `setup_vasp_inputs`：生成 POTCAR 与 POSCAR 拷贝；**INCAR** 中含 **`KSPACING`** 时**不**生成 **KPOINTS**
- Skill（`run_vasp`）：运行 VASP 前须载入全文并按 GPU/CPU 规则调用
- `Write` / `Edit`、`Bash`、`Read` / `Grep`

**VASP 启动（硬性）**：任何将执行 `mpirun`、直接调用 `vasp_std` / `vasp_gpu` 或等价命令的步骤，**必须先**通过工具调用 **`Skill: run_vasp`** 载入其全文，并按其中「核心执行准则」与用户已确认的 **GPU / CPU** 方案确定 `--np`、`--exe`、`--gpu-per-task`（及 `env_script`）。**严禁**在未执行上述步骤时，仅根据 `lscpu` 自拟大核数 `mpirun -np ...`。

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

**用户确认（总闸）**：未经用户明确同意，**不得**启动本 skill 中的任何收敛相关 VASP 计算。见下文 §0。

---

## 工作流步骤

### 0. 用户确认是否进行收敛测试（必经）

在读取准则、准备子目录或提交**任何** ENCUT/KSPACING 测试点之前：

1. 用**纯文本**向用户说明：截断能与 K 点收敛包含**多组**静态单点计算（`NSW=0`），**机时与排队成本较高**，且需按规则逐步完成。
2. **明确询问**用户：**是否要进行**完整的 **ENCUT 与 KSPACING 收敛测试**。
3. **停止生成**，等待用户在终端回复。**仅当**用户给出**明确肯定**（如「是」「做」「确认进行」「要」）后，才进入 §1 及以后。
4. 若用户**拒绝、暂缓或选择跳过**：
   - **禁止**启动本 skill 中的收敛扫描及任何与之相关的 VASP；
   - 在对话或工作区说明中记录「用户选择不进行收敛测试」；
   - 若仍有下游任务需要 **ENCUT/KSPACING**，仅可使用用户**显式指定**的数值，或模板/文献**初值**，并在文档中注明**未做系统收敛**。
5. 若对话**上文已**包含用户对「进行 ENCUT/KSPACING 收敛测试」的明确同意，可用**一句话复述**该选择与成本后进入 §1，避免重复追问。

---

### 1. 准备结构与 INCAR 模板

1. 确认工作目录中有可靠的 **`POSCAR`**（来自 `get_poscar_from_md` 或用户路径）。
2. `Read templates/INCAR_static_convergence`，复制为工作区中的 **`INCAR`** 或 **`INCAR_template`**，按体系设置 **`ISMEAR` / `SIGMA`**、**`ISPIN` / `MAGMOM`** 等（与后续正式计算保持一致）。
3. 尚未有 **POTCAR** 时，可先调用 **`setup_vasp_inputs`**（传入 `poscar_path` 与 `incar_path`）生成 **POTCAR**；**INCAR 须含 `KSPACING`**（模板已预留占位符），以便不写 **KPOINTS**。

---

### 2. 读入收敛准则

`Read references/convergence_rules.md`，掌握：

- **ENCUT** 扫描起点与示例序列；
- **`KSPACING`** 推荐序列与下限警告（勿低于 **0.08** 以免网格过大）；
- **1 meV/atom** 判据及「ENCUT 取较大、KSPACING 取较小」的惯例。

---

### 3. 逐点提交 ENCUT 与 KSPACING 测试

**目标**：得到满足 **≤ 1 meV/atom**（相邻测试步之间）的 **`ENCUT`** 与 **`KSPACING`**。

**执行方式（任务并行 vs 单作业内串行）**：

- **允许**：多个彼此独立的测试点作为**多个独立任务**并行提交（各子目录各自一次 `run_vasp`/作业）。
- **禁止**：**单个** Bash/Python 脚本、**单次**作业或**同一进程**内用 `for`/`while` **串行**跑完所有测试点。
- 判定：各点计算**结束后**再读能量；若下一步依赖上一步结果，由 Agent **逐步推理**，与「多点可否并行」不矛盾。

**建议目录布局**（可在当前 workspace 根目录或 `convergence_test/` 下）：

```text
convergence_test/
├── POSCAR
├── INCAR_template
├── encut_test/e_<ENCUT>/
└── kspacing_test/k_<KSPACING>/
```

每个子目录内：放入对应 **POSCAR**、**INCAR**（该点上的 **ENCUT** 或 **KSPACING**），调用 **`setup_vasp_inputs`**（保证 **KSPACING** 在 INCAR 中、且无多余 **KPOINTS**），再 **`run_vasp`**。算完后：

```bash
python /path/to/encut_kspacing_convergence/scripts/check_convergence.py .
```

若 `electronic_converged` 为 false，勿用于收敛判定；先按 `references/convergence_rules.md` 与项目内其它 troubleshooting 调整 **NELM** / **ALGO** 等后重算该点。

---

### 4. 写出报告

`Write Convergence_Report.md`（或 `convergence_test/Convergence_Report.md`），至少包含：

- 选定 **`ENCUT`**、**`KSPACING`**；
- 各测试步的总能量与 **ΔE (meV/atom)** 表；
- 测试用的 **POSCAR** 来源说明。

---

### 5. 交付物

向用户或下游 skill 明确给出：

- 推荐 **`ENCUT`**、**`KSPACING`**（及 **`KGAMMA`** 是否与测试一致）；
- **`Convergence_Report.md`** 路径；
- 提醒：后续所有需可比能量的静态计算须使用**相同** **ENCUT / KSPACING / POTCAR 类型**。

---

## 核心原则

- **用户确认**：未经用户明确同意，**不得**执行收敛测试或代为提交相关 VASP；§0 为硬性步骤。
- **静态单点**：收敛测试全程 **`NSW = 0`**，不在此阶段做离子步或变胞。
- **K 点仅用 INCAR**：依赖 **`KSPACING`**；**`setup_vasp_inputs`** 在含 **`KSPACING`** 时不写 **KPOINTS**；若目录中有旧 **KPOINTS**，应删除以免覆盖 INCAR。
- **禁止 monolithic 多点 VASP**：禁止单脚本单作业内顺序跑满多组 ENCUT/KSPACING；允许多个独立任务并行。

---

## 与其它 Skill 的关系

- **`lattice_constant`**：EOS 流程在缩放体积**之前**应先完成本 skill（或等价步骤），再将得到的 **ENCUT/KSPACING** 填入 **`INCAR_static`**。
- 仅当用户只要收敛参数、不要平衡晶格常数时，**只执行本 skill 即可**。
