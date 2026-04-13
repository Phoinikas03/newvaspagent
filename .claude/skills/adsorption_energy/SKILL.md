---
name: "vasp-adsorption-energy"
description: "执行 VASP 分子在表面吸附能计算的三步几何优化工作流：气相分子、洁净表面、吸附复合体系；由总能量按 E_ads=E(adsorbed)−E(molecule)−E(surface) 得到吸附能。当用户要求计算吸附能、吸附能差、CO（或其它分子）在金属/氧化物表面吸附、或搭建与 VaspAgent absorptionE 类 benchmark 一致的三段式算例时触发该技能。"
version: "1.0.0"
---

# VASP 吸附能计算工作流 (Adsorption Energy Workflow)

你是一个专业的计算材料学专家。本 Skill 指导完成 **吸附能** 的标准定义：**三次独立的几何优化**（气相分子、表面、吸附体系），再用三次自洽总能按固定公式相减。**不**将三步合并为单次 SCF。

## 目录结构

```
adsorption_energy/
├── SKILL.md                              ← 本文件（工作流指令）
├── scripts/
│   └── extract_absorption_energy.py      ← 从三份 OSZICAR 读 E0，算 E_ads，输出 JSON
├── references/
│   ├── incar_adsorption.md               ← 三步 INCAR 共性（ISIF、自旋、表面等）
│   └── troubleshooting.md                ← 能量可比性、符号、收敛问题
└── templates/
    └── INCAR_geom_opt                    ← 几何优化起点模板（需按体系改参数）
```

## 与参考实现（VaspAgent absorptionE）的对应关系

- 子目录命名惯例：**`CO`**（气相）、**`surface`**（表面）、**`absorbed`**（吸附复合），每目录内一次 VASP 优化后产生 **`OSZICAR`**。
- 后处理与 `calc_absorption_energy.sh` 等价：取各 **`OSZICAR`** 中最后一行 **`E0=`**，算 **`E3 - E1 - E2`**（E1=CO，E2=表面，E3=吸附）。
- 若用户使用 **`python op.py <子目录> POTCAR-xxx POSCAR-xxx`** 类脚本，须保证与上述子目录名及 **POTCAR/POSCAR** 成对关系一致。

## 可用工具

- `get_poscar_from_md`：获取体相或原型结构（表面 slab 常需用户或 `Skill`（`supercell`）进一步处理）
- `Skill`（`supercell`）：构建超胞或 slab（若任务涉及）
- `Skill`（`relax`）：若用户仅有未松弛的体相，可先松弛再切表面（依用户目标决定）
- `Skill`（`convergence`）：在固定几何下做 **ENCUT/KSPACING** 收敛（`NSW=0`），供三步优化 **共用** 同一截断能与 K 点密度；**须先征得用户同意**再执行（见该 skill §0）
- `setup_vasp_inputs`：生成 POTCAR；若 **INCAR** 含 **`KSPACING`** 则**不**生成 **KPOINTS**
- `Skill`（`run_vasp`）：**任何** `mpirun` / `vasp_std` / `vasp_gpu` 前必须载入并按 GPU/CPU 规则执行
- `Write` / `Edit`、`Bash`、`Read` / `Grep`
- `Skill`（`literature`）：检索吸附能实验或同类 DFT 工作对比时选用

注意：当前运行在无 GUI 的终端环境中。若需向用户提问，**直接输出纯文本问题并停止生成，等待用户在终端输入回复**。

**执行方式（与系统 ITERATIVE EXECUTION RULE 一致）**：**气相 → 表面 → 吸附** 三步为**三次独立 VASP 任务**；每一步须**单独提交**、结束后再检查收敛与 `OSZICAR`，再进入下一步。**严禁**用 Bash/Python 的 `for` 循环把三步串成一条命令无核查地跑完。允许的一次性脚本仅限本 skill `scripts/` 中的 **`extract_absorption_energy.py`**（后处理，不调用 VASP）。

---

## 工作流步骤

### 1. 确认化学图像与文件

询问并确认：

- **吸附质**：例如 CO 或其它分子；是否有 **ZPE / 熵** 校正需求（本 skill 默认为 **0 K 静态吸附能**，不含振动校正；若用户需要，须说明需额外频率计算，不在本 workflow 内展开）。
- **表面**：元素、晶面、slab 层数、真空厚度是否已有共识或文献依据。
- **输入来源**：用户是否已提供三套 **POSCAR**/**POTCAR**，或需从数据库/构建生成。

若结构未就绪，协调 **`relax`** / **`supercell`** / 用户手动切 slab，再进入第 2 步。

---

### 2.（可选）ENCUT / KSPACING 收敛

若用户需要与文献或发表级计算可比的 **ENCUT** 与 **KSPACING**：

1. **先询问**是否进行收敛测试（多步静态、`NSW=0`、机时成本），**停止并等待回复**。
2. 仅当用户**同意**后，载入 **`Skill: convergence`**，对**代表体系**（如已弛豫的 slab POSCAR）做收敛，得到 **`Convergence_Report.md`**。
3. 将选定的 **ENCUT**、**KSPACING** 用于**全部三步**几何优化 **INCAR**，并在说明文档中记录。

若用户拒绝，使用模板或用户指定数值，并在 **`adsorption_INCAR_notes.md`** 中注明未做系统收敛。

---

### 3. 准备三套计算目录与输入

为三步分别建立工作子目录（名称建议与参考实现一致）：

| 子目录（建议名） | 内容 |
|------------------|------|
| `CO` | 气相分子 **POSCAR**（足够大真空盒）、对应 **POTCAR** |
| `surface` | 洁净 slab **POSCAR**、**POTCAR** |
| `absorbed` | 吸附构型 **POSCAR**、**POTCAR**（与 surface 同一 slab 约定） |

调用 `setup_vasp_inputs` 或为每步复制匹配的 **POTCAR**。**三步的 ENCUT、泛函、POTCAR 类型必须一致**（除非用户书面要求不同策略）。

---

### 4. 编写三步 INCAR

1. `Read references/incar_adsorption.md`，`Read templates/INCAR_geom_opt`，按材料类型填写 **`ISMEAR`/`SIGMA`**、是否 **`ISPIN`/`MAGMOM`**、**`ISIF=2`**（固定晶胞仅移离子）等。
2. 若用户要求「不自旋」「不优化晶胞」「放宽力收敛」等，写入 **`adsorption_INCAR_notes.md`** 并与 INCAR 一致。
3. 每步 **`Write`** 该子目录下的 **`INCAR`**（可共享同一逻辑，但路径需在各自目录内）。

---

### 5. 依次运行 VASP（三步三任务）

对 **`CO`**、**`surface`**、**`absorbed`** **分别**：

1. 载入 **`Skill: run_vasp`**，按准则确认 **`np`** / **`--exe`** / GPU 映射。
2. 在该子目录下提交计算并等待完成。
3. 用与 **`relax`** 一致的方式检查离子步是否收敛（可读 **`OUTCAR`** / 项目内 `check_convergence.py` 若可用）；未收敛则 **`CONTCAR`→`POSCAR`** 续算，**禁止**未收敛就进入下一步。

---

### 6. 提取吸附能

三步均成功后，在工作区根目录（含 `CO/`、`surface/`、`absorbed/`）执行：

```bash
python .claude/skills/adsorption_energy/scripts/extract_absorption_energy.py --base .
```

或显式指定路径：

```bash
python .claude/skills/adsorption_energy/scripts/extract_absorption_energy.py \
  --co-dir ./CO --surface-dir ./surface --adsorbed-dir ./absorbed
```

从 JSON 读取 **`absorption_energy_eV`**（即 **E3−E1−E2**），并汇报 **`E_CO_eV`**、**`E_surface_eV`**、**`E_adsorbed_eV`**。

若 **`ok`: false**，`Read references/troubleshooting.md` 排查 **OSZICAR** 与路径。

---

### 7. 结果汇报

向用户说明：

- 吸附能数值（eV）及符号约定（本 workflow：**E_ads = E(adsorbed) − E(molecule) − E(surface)**）。
- 三步是否均离子收敛；关键文件路径（各目录 **`INCAR`、`OSZICAR`、`CONTCAR`**）。
- （可选）调用 **`Skill: literature`** 做实验或文献对比时，明确检索目标与材料体系。

---

## 核心原则

- **三步三算**：吸附能必须由**三次**优化后的总能相减得到；禁止单步能量拆解近似替代。
- **参数可比**：默认 **ENCUT、KSPACING/ K 点、泛函、POTCAR** 在三步间一致；**真空与 slab 设定**在表面与吸附两步间一致。
- **禁止 monolithic 无核查批跑**：不得用单个 `for` 循环连续提交三步而不做逐步收敛检查。
- **run_vasp 前置**：任何 VASP 启动前必须载入 **`run_vasp`** 并遵守硬件与确认规则。
- **收敛前置需同意**：正式使用前若要做 **ENCUT/KSPACING** 系统收敛，**须用户明确同意**后再载入 **`convergence`**。
- **参数先查本地**：先查 **`references/incar_adsorption.md`** 与 **`troubleshooting.md`**；疑难再 **`literature`** 或联网。
