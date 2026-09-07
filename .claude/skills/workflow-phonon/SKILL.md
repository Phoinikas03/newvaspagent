---
name: "workflow-phonon"
description: "执行 VASP 声子谱工作流：结构弛豫 → 超胞有限位移力计算 → phonopy 拟合力常数 → 声子色散谱与态密度（含 LO-TO 劈裂 NAC 修正）→ 与实验对比。当用户要计算声子色散曲线、声子态密度 (phonon DOS)、声子频率、声子谱、晶格动力学、NAC/LO-TO 劈裂，或要求产出 phonon band/DOS 图时触发。使用 phonopy（v4+）与 VASP 有限位移法；涉及 ionic 晶体时须做 Born 有效电荷 + 介电张量的 DFPT 计算。运行 VASP 前必须经过 run-vasp，涉及 GPU/KPAR/NCORE 时须先经过 incar-performance。"
---

# VASP 声子谱计算工作流（Phonon Dispersion & DOS）

你是一个专业的计算材料学专家。这个 Skill 指导你自动化完成固体的声子色散谱与声子态密度计算。核心方法是**有限位移法（finite-displacement / frozen-phonon）**：在平衡结构上构建超胞，对等效原子做小位移，用 VASP 计算位移构型上的 Hellmann-Feynman 力，再交给 **phonopy** 拟合谐波力常数、沿高对称路径计算色散、并在 Γ 点附近用 **NAC（非解析项修正，BORN 文件）** 复现离子晶体的 LO-TO 劈裂。

## 何时触发

- 用户要求计算**声子色散曲线 / 声子谱 / phonon dispersion**
- 用户要求计算**声子态密度 / phonon DOS / 声子能态**
- 用户要求**声子频率、晶格动力学、晶格振动、热力学性质**（晶格热容、零点能）
- 用户在已知结构上要做声子计算，尤其是**离子晶体**（需要 LO-TO 劈裂）
- 需要与实验（INS / Raman / IR）声子频率对比的基准计算

## 依赖的已有 skill（前置加载）

本 skill **不负责** VASP 输入生成与运行。执行前必须先加载：

- **`Skill: run-vasp`** — 任何 VASP / mpirun / vasp_gpu / vasp_runner.py 运行前**必须**加载。遵循其探针、STRICT HARDWARE ALIGNMENT（GPU 与 CPU、1 rank↔1 GPU）、`vasp_runner.py --dirs` 分批策略。
- **`Skill: incar-builder`** — 写或改 INCAR 前**必须**加载。
- **`Skill: structure-builder`** — 获取/构造 POSCAR 前**必须**加载（本 skill 不从记忆手写 POSCAR）。
- **`Skill: incar-performance`** — 涉及 GPU / KPAR / NCORE / NPAR 前加载。
- **`Skill: incar-smearing-precision`**、**`Skill: incar-validator`** — 设置与校验精度时加载。
- **`Skill: workflow-relax`** — 平衡结构松弛（Stage A）。
- **`Skill: workflow-convergence`** — ENCUT / KSPACING 收敛测试（决定生产 ENCUT / KSPACING）。
- **`Skill: research-literature`** — 检索实验声子频率做对比基准；也可用 `duckduckgo_search` / `semanticscholar_search` / `arxiv_search` 检索。

## 目录结构

```
workflow-phonon/
├── SKILL.md                ← 本文件（声子工作流）
├── scripts/
│   ├── build_conventional_cell.py  ← pymatgen 原胞 → 常规胞（若单元胞是原胞 / 低对称）
│   ├── get_born_params.py          ← 构建 phonopy nac_params dict（手动解析 BORN，避开 parse_BORN 坑）
│   ├── plot_phonon_dos.py          ← 由 FORCE_CONSTANTS + BORN 出色散 + DOS 图（v4 Python API，含 NAC）
│   └── extract_phonon_report.py    ← 从 band/DOS 提取高对称点频率与 DOS 峰，供实验对比
└── references/
    └── vasp_phonopy_settings.md   ← 声子各阶段 INCAR 关键 tag（DFPT/力计算/收敛）
```

## 工作流程总览

```
Stage A  结构弛豫          → workflow-relax 得到平衡晶格常数
Stage B  收敛测试          → workflow-convergence 定 ENCUT / KSPACING（1 meV/atom）
Stage C  确定原胞 vs 常规胞 → 决定超胞方案与 BORN 匹配
Stage D  DFPT 介电/Born    → LEPSILON 静态 → phonopy-vasp-born 生成 BORN（无 BORN 则跳过 NAC）
Stage E  超胞位移构型      → phonopy-init --dim ... -d 生成 SPOSCAR + POSCAR-###
Stage F  批量力计算        → vasp_runner.py 每个位移构型跑静态力（IBRION=-1, NSW=0）
Stage G  提取 FORCE_SETS   → phonopy-init -f vasprun.xml...
Stage H  拟合 FORCE_CONSTANTS → phonopy --writefc --fc-spg-symmetry
Stage I  色散 + DOS 绘图    → 脚本读 FORCE_CONSTANTS + BORN → band/DOS 图（v4 API）
Stage J  实验对比 + 报告    → 提取关键点频率 → Phonon_Report.md
```

**阶段间确认门**：Stage A / D / E / F 是吃机时节点，开跑前向用户汇报计划并征得同意（见「执行方式」）。

---

## 核心原则（先读再动）

### PRINCIPLE 1：有限位移法不允许任何弛豫
位移构型上的 VASP 力计算**必须**是静态单点：`IBRION=-1`、`NSW=0`、`ISIF=2`。任何原子弛豫都会破坏有限位移法的线性响应假设，得到错误的力常数。力计算的精度直接决定声子质量，因此电子收敛要严：`EDIFF=1E-6`、`PREC=Accurate`。

**为什么**：有限位移法的核心是把测得的力当作"该位移下晶格的恢复力"。若原子在被测构型里又弛豫了，测的就只是弛豫后的另一套结构，不是位移构型本身的力，二阶力常数矩阵随之失真。

### PRINCIPLE 2：原子位移必须小且对称利用
phonopy 默认位移幅度 **0.01 Å**（不破坏谐波近似 / 线性响应），足够大以免力被数值噪声淹没。phonopy 会自动利用点群对称性把超胞内等效原子约化成**少量独立位移**（MgO 岩盐 64 原子超胞只生成 **2 个独立位移**）。**不要手动增加位移数**，那会白费机时且不提升精度。

### PRINCIPLE 3：离子晶体必须有 NAC（LO-TO 劈裂）
极性/离子晶体（MgO、ZnO、GaN、钙钛矿等）在 Γ 点存在 **LO-TO 劈裂**，必须用 **BORN 文件**（Born 有效电荷 + 介电张量）做非解析项修正。若无 BORN 文件，声子在 Γ 处光学支会被错误地简并（劈裂 = 0）。**BORN 通过一次 DFPT（`LEPSILON=.TRUE.`）计算得到**，见 Stage D。

**为什么**：非解析项来自长程偶极-偶极相互作用，它使纵光学支（LO）在长波极限不同于横光学支（TO）。这一项是 q→0 的极限贡献，只有读入 Born 电荷 + 介电张量才能正确计入。

### PRINCIPLE 4：原胞 vs 常规胞 —— 先想清楚再生成
音子计算的标准输入是**主胞 + 超胞矩阵**，但 BORN 文件必须与**主胞的原子数**匹配。两条路线：
- **路线 1（推荐，MgO 等）**：用**常规胞**（如岩盐 Mg4O4，8 原子）做单元胞，phonopy 声明 `primitive_matrix`（fcc 基变换）还原到原胞，超胞 `--dim 2 2 2` = 64 原子。BORN 用 8 原子版。
- **路线 2**：用**原胞**（2 原子）做单元胞，超胞取更大 `--dim`（如原胞 --dim 3 3 3 = 54 原子）以保证力常数收敛。BORN 用 2 原子版。

关键：**BORN 的原子数必须等于 ph.primitive 的原子数**，且 POSCAR 的原子顺序与 BORN 一致。选择时以"超胞足够大收敛力常数、且 BORN 与主胞匹配"为准。

---

## Stage A：结构弛豫（平衡晶格常数）

1. 从 `structure-builder` 获取初始结构（MP mp-id 或用户提供 POSCAR）。
2. 若拿到的是**原胞**且最终要算声子，把它转成**常规胞**（用 `structure-builder` / pymatgen，见下方「常规胞构造」）。
3. 用 **`workflow-relax`** 做 `ISIF=3` 全弛豫，得到平衡晶格常数。

**⚠️ pymatgen 坑**：`Structure.get_conventional_standard_structure()` 在较新 pymatgen 已改名为 `get_conventional_standard_structure()` 且可能不可用 / 行为改变。**不要依赖它**。可靠做法是手写 `Structure.from_file` + `Lattice.cubic(a)` 构造常规立方胞（岩盐/萤石等标准结构），或用 `pymatgen.symmetry.analyze` 相关接口。复杂结构仍可用 MP 的常规胞（`cif`/POSCAR 已是常规胞）。

## Stage B：ENCUT / KSPACING 收敛

用 **`workflow-convergence`** 在**单胞**上做 ENCUT 与 KSPACING 收敛（标准：相邻步 ΔE ≤ 1 meV/atom 后取较大者）。收敛得到的 ENCUT / KSPACING 用于后续所有阶段（DFPT、力计算），保证能量/力基准一致。

## Stage C：确定超胞方案

- 明确单元胞是**原胞还是常规胞**；明确 `primitive_matrix`（若用常规胞还原到原胞）与 `--dim` 超胞矩阵。
- 核对超胞大小（原子数），确保位移构型不因超胞过大而机时爆炸；MgO 常规胞 `--dim 2 2 2` = 64 原子是合理基准。
- 记录最终要用于 phonopy 的 `POSCAR-unitcell`（单元胞 POSCAR）与 BORN 匹配关系。

---

## Stage D：DFPT 介电张量 + Born 有效电荷（生成 BORN）

离子晶体才需要。若体系为非极性（如石墨、硅），**跳过本阶段**，不对 BORN 做 NAC。

### D1. DFPT 静态 INCAR
在**松弛后的单元胞**上做一次 DFPT：
```
IBRION = -1   ; NSW = 0     ; ISIF = 2
LEPSILON = .TRUE.          ; # DFPT 介电张量 + Born 有效电荷
PREC = Accurate ; EDIFF = 1E-6
ENCUT = <收敛值> ; KSPACING = <收敛值>   ; # DFPT 介电比能量慢，用收敛值
ISMEAR = 0 ; SIGMA = 0.05
LWAVE = .FALSE. ; LCHARG = .FALSE.
```
设置生成 INCAR 时用 `incar-builder` + `incar-performance`；POTCAR/POSCAR 用 `setup_vasp_inputs`。

**为什么 KSPACING 要用收敛值而非更粗**：介电张量与 Born 电荷对 k 网格的收敛比总能量慢，用能量收敛的粗网格会低估介电常数，导致 LO-TO 劈裂偏小。

### D2. 生成 BORN 文件
```bash
cd <lepsilon dir>          # 确保 cwd 里有写完的 vasprun.xml
phonopy-vasp-born > BORN   # ⚠️ 必须重定向！它只打印到 stdout，不会写文件
```
**⚠️ 坑**：`phonopy-vasp-born` **不会自动写出 BORN 文件**，而是把介电张量和 Born 电荷打印到 stdout。必须 `> BORN` 重定向保存。它会给出这样的两类行（第 1 行介电张量 9 个数，之后每原子 9 个数）：
```
# epsilon and Z* of atoms ...
   3.233  0.0  0.0  0.0  3.233  0.0  0.0  0.0  3.233
   1.992  0.0  0.0  0.0  1.992  0.0  0.0  0.0  1.992
  -1.992  0.0  0.0  0.0 -1.992  0.0  0.0  0.0 -1.992
```
**物理校验**：MgO 理论 Born 电荷 ≈ ±2，介电张量各向同性 ≈ 3.0。若数值偏离一个数量级，通常是 DFPT 未收敛或 vasprun.xml 未写完就跑了该工具。

### D3. 等待 DFPT 真正完成
不要把监测器设成"匹配到 BORN 字符串"——VASP 的 INCAR 里可能有 `SYSTEM = ... BORN ...` 或 `LEPSILON` 字样导致**误判完成**。正确等待条件是 OUTCAR 出现 `General timing` / `Total CPU time` 且 `vasprun.xml` 已写完。

---

## Stage E：生成超胞位移构型

用 `phonopy-init`（**v4 起 `--dim`、`-d`、`--symmetry` 都从 `phonopy` 主命令移到 `phonopy-init`**）：

```bash
cd <disp dir>
# 单元胞：常规胞还是原胞（与 BORN 匹配）
cp <relax>/CONTCAR POSCAR-unitcell        # 若松弛的是常规胞且要与 BORN 匹配
# 生成超胞 + 位移构型 + SPOSCAR
phonopy-init --dim 2 2 2 -c POSCAR-unitcell -d
```
产物：
- `SPOSCAR` 超胞
- `POSCAR-001`、`POSCAR-002` ... 每个独立位移一个（MgO 64 原子超胞 → 2 个）
- `phonopy_disp.yaml` 记录位移信息（Stage G 提取力要用）

**确认位移数**：`ls POSCAR-*` 数目应与对称性约化后的独立位移数一致，不要人为增加。
**确认超胞原子数**：读 `SPOSCAR` 前几行核对原子总数（常规胞 8 原子 × 8 = 64）。

---

## Stage F：批量运行力计算

每个位移构型一个目录（如 `fc/fc_001`、`fc/fc_002`），内含该构型的 POSCAR + 统一的力计算 INCAR + POTCAR。用 `setup_vasp_inputs`（`work_dir`）生成每个目录的 VASP 输入。

力计算 INCAR：
```
IBRION = -1 ; NSW = 0 ; ISIF = 2      ; # 严禁任何弛豫
PREC = Accurate ; EDIFF = 1E-6
ENCUT = <收敛值> ; KSPACING = <收敛值>
ISMEAR = 0 ; SIGMA = 0.05
LWAVE = .FALSE. ; LCHARG = .FALSE.
```

**运行**：加载 `run-vasp`，用 `vasp_runner.py` 一次提交所有位移构型目录：
```bash
python .claude/skills/run-vasp/scripts/vasp_runner.py \
  --dirs <abs>/fc/fc_001 <abs>/fc/fc_002 ... \
  --mode local --np 1 --exe vasp_gpu --gpu-per-task 1 --fixed-gpu-layout \
  --env-script /abs/template/env_gpu.sh --log-prefix vasp_fc
```
**⚠️ 一律用绝对路径**给 `--dirs`。`vasp_runner.py` 从仓库根解析相对路径，传相对路径会跑到错误目录（报 "No INCAR found"）。

**⚠️ 等待任务用 `until` 循环 / Monitor，不要用前台 `sleep`**（会被 Bash 工具拦截）。后台跑长任务用 `run_in_background: true`。

---

## Stage G：提取 FORCE_SETS

从所有位移构型的 `vasprun.xml` 提取力，生成 `FORCE_SETS`。要把 `phonopy_disp.yaml` 一起放到 fc 目录（phonopy 需要它读位移信息）：

```bash
cp <disp>/phonopy_disp.yaml <fc>/phonopy_disp.yaml
cp <disp>/SPOSCAR <fc>/SPOSCAR
cd <fc>
phonopy-init -f fc_001/vasprun.xml fc_002/vasprun.xml
```
生成 `FORCE_SETS`。核对大小（约 2 位移 × 64 原子 × 3 力分量）。

---

## Stage H：拟合力常数 FORCE_CONSTANTS

`phonopy` 主命令默认从当前目录的 `FORCE_SETS` + `SPOSCAR` 读取，用 `--writefc` 写 `FORCE_CONSTANTS`，用 `--fc-spg-symmetry` 做空间群对称化：

```bash
cd <fc>
phonopy --writefc --fc-spg-symmetry
```
**⚠️ v4 关键变更**（这是本 skill 捕捉到的最大坑）：
- `phonopy --dim` → **已移除**，只在 `phonopy-init`
- `phonopy --nac` → **已移除**，NAC 在读入 BORN 文件后**自动启用**（无需 `--nac`）
- `phonopy --fc-symmetry` → 改为 **`--fc-spg-symmetry`**（主命令），或直接用 Python API 的 `ph.force_constants = fc`
- **FORCE_CONSTANTS 拟合只需在含 FORCE_SETS + SPOSCAR 的目录里跑 `phonopy --writefc`**，别把 `--dim` 塞进来

产物：`FORCE_CONSTANTS` + `phonopy.yaml`（若目录里有 BORN，`phonopy.yaml` 会含 `nac:` 段）。

---

## Stage I：色散 + DOS 绘图（v4 Python API）

用 Python 的 phonopy API 一步出图最稳。**不要用已被移除的方法**（见「API 坑」），正确模式是：

```python
import numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from phonopy import Phonopy
from phonopy.interface.vasp import read_vasp
from phonopy.file_IO import parse_FORCE_CONSTANTS

unitcell = read_vasp("../disp/POSCAR-conv")   # 单元胞（与 BORN/原始胞对得上）
ph = Phonopy(unitcell,
             supercell_matrix=np.diag([2,2,2]),
             primitive_matrix=[[0,.5,.5],[.5,0,.5],[.5,.5,0]])  # fcc 基
ph.force_constants = parse_FORCE_CONSTANTS("FORCE_CONSTANTS")   # ← 属性，非方法

# NAC：手动构建 nac_params dict（最稳）
nac_params = build_nac_params(ph)   # 见 get_born_params.py
if nac_params: ph.nac_params = nac_params

# 色散
band_paths = [np.linspace(p0,p1,101) for p0,p1 in seg_pts]  # Γ-X-W-Γ-L
bs = ph.run_band_structure(band_paths, with_eigenvectors=False,
                           labels=['Γ','X','W','L'], path_connections=[...])
# bs.distances / bs.frequencies / bs.path_connections

# DOS
ph.run_mesh([31,31,31], with_eigenvectors=False, is_mesh_symmetry=True)
dos = ph.run_total_dos(freq_min=-0.3, freq_max=22.0, freq_pitch=0.05,
                       use_tetrahedron_method=True)
```

**NAC 的坑（关键）**：
- `from phonopy.file_IO import read_BORN` → **不存在**，`parse_BORN` 的签名/字段又和预期不同（返回的 NacParams 缺 `factor`）。
- **最稳做法是手动解析 BORN 文件**构建 `nac_params` dict，包含 `born`、`dielectric`、`factor`（phonopy 惯例 **14.399652**）、`primitive`、`q_direction`。见 `scripts/get_born_params.py`。

**⚠️ 频率提取与 LO-TO**：`run_qpoints` 在 **Γ 点 (0,0,0) 处不应用 NAC**，LO 与 TO 会显示为同一频率（劈裂=0）。要得到含 NAC 劈裂的高对称点频率，**必须用 `run_band_structure` 或带 q 方向微扰的处理**。这意味着：画图 + 提取各处频率应统一用 **band 结构数据**，不要用 qpoints 数据。

**频率单位**：phonopy 内部用 THz（DOS 轴的 freq 也是 THz）。画图时常乘 `CM_PER_THZ = 33.356` 转 cm⁻¹。把 `freq * cm` 用于 y 轴与报告。

---

## Stage J：实验对比 + 报告

1. 用 `scripts/extract_phonon_report.py` 从 band 结构提取各高对称点频率、从 DOS 提取峰值。
2. 检索文献/实验基准（`research-literature`、`duckduckgo_search`、`semanticscholar_search`），得到实验声子频率（MgO：Γ TO≈401 cm⁻¹，LO≈720 cm⁻¹，Sangster INS）。
3. 写 `Phonon_Report.md`：结构、收敛 ENCUT/KSPACING、DFPT 介电/Born、色散与 DOS 图路径、高对称点频率表、与实验对比及偏差分析。

**⚠️ LO-TO 劈裂 = 0 的排查**：若 Γ 处光学支出现 LO=TO（劈裂=0）：
- 检查 `phonopy.yaml` 是否有 `nac:` 段（有 BORN 才有）。没有 → 说明 `ph.nac_params` 没设，或 FORCE_CONSTANTS 拟合时目录里没 BORN。
- 确认 `nac_params` 的 `factor` 与 `dielectric`/`born` 数值正确。
- 用 band 结构而非 qpoints 提取频率。

---

## 执行方式（ITERATIVE EXECUTION RULE）

与仓库 system_prompt 一致：
- **禁止**用 `for`/`while` 或 monolithic Python/Bash 脚本一次提交多点、多阶段、多目录的 VASP 计算。
- 每个重步骤（每个收敛点、每个位移构型）**单独**用 `run_in_background: true` 提交，或走 `vasp_runner.py --dirs` 把同批次目录交给 runner 分批调度。
- 每步跑完**先读 OUTCAR / OSZICAR / 收敛报告**确认收敛与正确性，再决定下一步。
- **开跑前向用户展示完整 `vasp_runner.py` 命令并征得同意**（含 `--env-script`、`--gpu-per-task`、`--fixed-gpu-layout`）。
- GPU 与 CPU 并存时**不要默认 CPU**，先问用户 GPU vs CPU 及 GPU 数。
- 有调度器时问 partition / nodes / walltime。
- 等待用 `until` 循环 / Monitor / `run_in_background`，**不要前台 `sleep`**。

### STRICT HARDWARE ALIGNMENT
遵循 `run-vasp`：1 rank ↔ 1 GPU；GPU 卡数 = 并行任务数（如 2 个位移构型 = 2 卡）。`vasp_gpu` 在无 tty 的 `start_new_session` 下可能因 OpenMPI cwd 解析问题报 "No INCAR found"，此时给 runner 传**绝对路径** `--dirs` 即可。本地多卡用 `--gpu-per-task 1` + `--fixed-gpu-layout`。

---

## VASP 文件来源（provenance）

- **POSCAR / POTCAR / KPOINTS**：一律不手写。通过 `structure-builder` 获取结构 + `mcp__vasp_agent__setup_vasp_inputs`（可传 `work_dir` 为每个位移构型/目录单独生成 POTCAR/POSCAR/INCAR）。POTCAR 用 pymatgen/MP **推荐**半芯势（Mg_pv、O 等），仅当用户明确指定时才 `potcar_overrides`。
- **INCAR**：可复制本 skill 模板或 `workflow-relax` 模板修改（ENCUT / ISMEAR / KSPACING / IBRION / NSW 等），不手写 POSCAR。

---

## 关键坑速查（为何）

| 症状 | 原因 | 规避 |
|---|---|---|
| `phonopy: error: '--dim' is a setup operation` | v4 把 setup 操作移到 `phonopy-init` | 用 `phonopy-init --dim ... -d` |
| `'--nac' was removed in phonopy v4` | NAC 自动启用 | 目录放 BORN，不加 `--nac` |
| `'--fc-symmetry'` 不被接受 | 主命令改名 `--fc-spg-symmetry` | 用 `phonopy --writefc --fc-spg-symmetry` |
| `Phonopy(...) unexpected keyword 'factor'` | v4 构造函数无 factor | factor 放进 `nac_params` |
| `Phonopy has no 'load_force_constants'` | v4 用属性 | `ph.force_constants = parse_FORCE_CONSTANTS(...)` |
| `cannot import read_BORN` / `parse_BORN` 缺字段 | 字段变化 | 手动解析 BORN 构建 `nac_params`（get_born_params.py） |
| `phonopy-vasp-born` 没写 BORN | 只打印 stdout | `phonopy-vasp-born > BORN` |
| LO-TO 劈裂 = 0（甚至 qpoints 里） | `run_qpoints` 在 Γ 不应用 NAC | 用 `run_band_structure` 提取 |
| 位移构型 VASP 报 "No INCAR found" | `--dirs` 相对路径解析歧义 | `--dirs` 用绝对路径 |
| vasp_gpu 启动报 MPI / help 文件缺失 | OpenMPI 前缀错位 | `--env-script` 设 `OPAL_PREFIX`；`run-vasp` 探针 |
| 监测器误报 DFPT 完成 | 匹配到 "BORN" 字样 | 等 `General timing` + vasprun.xml 写完 |
| 前台 `sleep` 被拦截 | Bash 工具规则 | `until` 循环 / Monitor / `run_in_background` |
| `get_conventional_standard_structure` 报错 | pymatgen API 变化 | 手动构造常规胞（build_conventional_cell.py） |

---

## 附：v4 phonopy API 可用成员速查

- 构造函数：`Phonopy(unitcell, supercell_matrix=..., primitive_matrix=...)`（无 `factor`）
- 力常数：读 `ph.force_constants = parse_FORCE_CONSTANTS("FORCE_CONSTANTS")`；写 `phonopy --writefc`
- NAC：`ph.nac_params = {born, dielectric, factor, primitive, q_direction}`
- 色散：`ph.run_band_structure(band_paths, with_eigenvectors=False, labels=..., path_connections=...)` → 返回对象的 `.distances` `.frequencies` `.path_connections`
- DOS：`ph.run_mesh([N,N,N], ...)`; `ph.run_total_dos(freq_min, freq_max, freq_pitch, use_tetrahedron_method=True)` → `.frequency_points` `.dos`
- 单位：`CM_PER_THZ = 33.356`

write 前先确认 phonopy 版本：`python -c "import phonopy; print(phonopy.__version__)"`。若 <4，上述 v4 行为不适用，改用旧语法（`--dim`、`--nac`、`--fc-symmetry`）。