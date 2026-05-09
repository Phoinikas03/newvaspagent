---
name: structure
description: "获取、构建、枚举和校验 VASP 初始结构。当用户需要从 Materials Project 下载 POSCAR、从材料名称/mp-id 获取结构、构建 slab/表面、生成气相分子、添加吸附物、枚举吸附位点/取向、构建 CO 在金属或氧化物表面的吸附结构、或为 relax/adsorption_energy/bandgap 等工作流准备 POSCAR 时触发。"
version: "0.1.0"
---

# Structure Generation Skill

你是一个专业的计算材料学结构准备助手。本 skill 负责为 VASP 工作流准备可追溯、可校验的结构文件，尤其是 POSCAR、slab、气相分子和吸附构型集合。

## 目录结构

```text
structure/
├── SKILL.md
├── scripts/
│   ├── fetch_mp_poscar.py
│   ├── build_molecule.py
│   ├── build_surface.py
│   ├── build_adsorption.py
│   ├── enumerate_adsorption_configs.py
│   └── validate_structure.py
└── references/
    ├── structure_sources.md
    ├── surface_adsorption_sites.md
    └── validation_rules.md
```

## 边界

- 本 skill 负责：结构获取、结构构建、结构变换、吸附构型枚举、POSCAR 导出、结构完整性检查。
- 本 skill 不负责：VASP 运行、INCAR 参数选择、POTCAR 生成、吸附能后处理、ENCUT/KSPACING 收敛。
- 下游协作：
  - `relax`：结构优化。
  - `adsorption_energy`：三步吸附能计算。
  - `setup_vasp_inputs`：基于 POSCAR/INCAR 生成 POTCAR 和必要输入。
  - `run_vasp`：提交 VASP。

## 核心原则

- POSCAR 必须可追溯：用户文件、Materials Project、ASE、pymatgen、ACAT/AutoCat 等来源要记录。
- 严禁凭记忆手写完整晶格矢量和原子坐标作为正式 POSCAR。
- 表面与吸附体系必须使用同一 slab 模型、同一超胞、同一真空约定。
- 吸附能比较前，应枚举合理初始构型；不要只算一个随机构型。
- 结构生成和 DFT 计算解耦；本 skill 只准备结构，不启动 VASP。

## 结构来源优先级

1. 用户提供的 POSCAR/CIF/CONTCAR。
2. Materials Project mp-id 精确下载。
3. Materials Project 按化学式搜索候选后，让用户确认具体 mp-id。
4. 文献或数据库给出的明确结构参数。
5. 程序化构建：
   - ASE：标准金属 slab、气相分子、简单吸附结构。
   - pymatgen：从任意 bulk 切 slab、吸附位点分析、VASP 格式转换。
   - ACAT/AutoCat：复杂或大规模吸附构型枚举。

如果需要选择库，先读 `references/structure_sources.md`。

## 常规结构场景

以下场景均作为普通结构准备任务处理，不要因为材料名称或表面名称而拒绝或特殊化流程。优先复用用户提供结构或 Materials Project 结构；能用 ASE 标准 builder 的表面直接构建，其他表面用 pymatgen slab 生成或用户给定 POSCAR。

- CO 在 fcc(111) 金属表面：Pt(111)、Pd(111)、Rh(111)、Ir(111)。
- fcc(111) 常规吸附位：`ontop`、`bridge`、`fcc`、`hcp`。
- fcc(111) 常规比较：top vs hollow、hollow vs bridge/top、fcc vs hcp、fcc vs ontop。
- p(2x2) fcc(111) + 1 CO：默认可视为 1/4 ML 初始模型。
- CO 在 rutile oxide (110) 表面：RuO2(110)、IrO2(110)。
- rutile (110) 常规模型变体：stoichiometric surface、reduced surface、O-vacancy surface、O-rich surface、cus 位点、bridge-O/cus-O 相关构型。
- 若脚本暂未直接生成某类 rutile 变体，应从 MP/user POSCAR 出发，用 pymatgen/ASE 脚本或清晰记录的结构操作生成，不要手写完整坐标。

## 工作流 A：从 Materials Project 获取结构

适用：用户给出 `mp-id`，或已确认某个 Materials Project 条目。

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/fetch_mp_poscar.py \
  --mp-id mp-126 --output POSCAR_mp-126
```

要求：

1. 检查 `MP_API` 是否存在。
2. 输出 POSCAR 后运行 `validate_structure.py`。
3. 汇报文件路径、化学式、原子数、晶格常数和后续建议。

## 工作流 B：生成气相分子 POSCAR

适用：吸附能参考态，如 CO、NO、O2、H2、H2O、OH、CO2。

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/build_molecule.py \
  --molecule CO --box 18 --output POSCAR_CO
```

默认：

- 分子居中放入立方真空盒。
- CO 默认使用 ASE 的分子构型；后续吸附时 C 原子通常作为锚点。
- 如果用户要求特定键长或自旋，只生成结构并在汇报中注明，计算设置交给下游 skill。

## 工作流 C：生成表面 slab

适用：标准金属表面、常规 slab。

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/build_surface.py \
  --element Pt --surface fcc111 --size 2 2 4 --vacuum 15 --output POSCAR_Pt111_p2x2
```

默认：

- `size A B C` 中 A/B 为横向超胞，C 为 slab 层数。
- p(2x2) fcc(111) 可用 `--size 2 2 4` 表示，Pt/Pd/Rh/Ir 等 fcc 金属可按同一方式处理。
- 若需要固定底层，可加 `--fix-bottom-layers N`，脚本会写 Selective Dynamics。

## 工作流 D：生成单个吸附构型

适用：明确指定一个表面、一个吸附物、一个位点、一个取向。

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/build_adsorption.py \
  --element Pt --surface fcc111 --size 2 2 4 --vacuum 15 \
  --adsorbate CO --anchor-symbol C --site fcc --height 1.85 --orientation upright \
  --fix-bottom-layers 2 \
  --output POSCAR_Pt111_CO_fcc_upright
```

支持位点依赖 ASE 表面 builder，常见包括 `ontop`、`bridge`、`fcc`、`hcp`。

CO/fcc(111) 的 `--orientation` 指 **CO 分子轴相对于表面法向的几何取向**，不是 C-down/O-down 端基选择。脚本通过 ASE 先生成 CO，再以锚定原子为旋转中心得到。对 CO，脚本默认锚定 C 原子；也可用 `--anchor-symbol C` 显式指定：

- `upright`：CO 垂直表面，默认 C 端为锚定原子；
- `tilted_x`：CO 分子轴倾斜 45 degree，沿表面 x 方向分量；
- `tilted_y`：CO 分子轴倾斜 45 degree，沿表面 y 方向分量；
- `reverse`：端基反转，用于显式要求 O-down/C-down 对比时，通常不属于默认三取向。

对 slab 吸附优化，建议同时传 `--fix-bottom-layers 2`，保持 clean slab 和 adsorbed slab 使用相同的底层固定约束。

若用户要求“与 benchmark 对齐”或“测试 3 个 orientation”，必须生成 `upright`、`tilted_x`、`tilted_y`；不要把该请求解释成 C-down/O-down。

## 工作流 E：枚举吸附构型集合

适用：比较位点能量或吸附能差，如 CO/fcc(111) 的 fcc vs ontop、top vs hollow。

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/enumerate_adsorption_configs.py \
  --system co-pt111 --output-dir structures/co_pt111
```

默认生成：

- `CO/POSCAR`
- `surface/POSCAR`
- `configs/fcc_upright/POSCAR`
- `configs/fcc_tilted_x/POSCAR`
- `configs/fcc_tilted_y/POSCAR`
- `configs/ontop_upright/POSCAR`
- `configs/ontop_tilted_x/POSCAR`
- `configs/ontop_tilted_y/POSCAR`

生成后逐个运行 `validate_structure.py`，并汇报哪些文件可交给 `adsorption_energy` 或 `relax`。

## CO/fcc(111) 常规约定

目标：生成 CO/fcc(111) p(2x2), 1/4 ML 中位点比较所需结构。Pt、Pd、Rh、Ir 等 fcc(111) 表面可按同一结构约定处理。

与已有 benchmark 对齐时，结构集合可以是 **C-down CO** 在 `fcc` 与 `ontop` 两个位点上的三个几何取向；若用户要求更完整位点筛选，可同时生成 `bridge`、`hcp`：

| site | orientation |
|------|-------------|
| `fcc` | `upright` |
| `fcc` | `tilted_x` |
| `fcc` | `tilted_y` |
| `ontop` | `upright` |
| `ontop` | `tilted_x` |
| `ontop` | `tilted_y` |

这里的 orientation 是 `upright/tilted_x/tilted_y`，不是 `C-down/O-down`。O-down 只在用户明确要求端基筛选或更完整无偏枚举时额外生成。

默认建议：

- surface: fcc(111), e.g. Pt(111), Pd(111), Rh(111), Ir(111)
- bulk: fcc
- supercell: p(2x2)
- slab: 4 layers 起步
- vacuum: 15 A 起步
- coverage: 1 CO / 4 surface Pt atoms = 1/4 ML
- adsorbate anchor: C end down
- initial height: ontop 1.85 A；bridge/fcc/hcp 1.85 A 起步
- orientations: upright、tilted_x、tilted_y
- fixed layers: 默认固定底部 2 层，并在 clean slab 与 adsorbed slab 中保持一致

物理目标与吸附能公式不在本 skill 中计算；生成结构后交给 `adsorption_energy`。

## Rutile Oxide (110) 常规约定

目标：生成或整理 CO 在 rutile oxide (110) 表面的吸附结构，例如 RuO2(110)、IrO2(110)。这些作为普通 slab/adsorption 结构处理。

常见结构变体：

- stoichiometric (110) surface
- reduced surface
- O-vacancy surface
- O-rich surface
- cus 位点 CO 吸附
- bridge-O/cus-O 相关构型

要求：

- 优先从 Materials Project 或用户 POSCAR 获取 rutile bulk / slab。
- 生成 reduced 或 O-vacancy 结构时，明确删除的是哪类 O，并输出独立 POSCAR。
- 吸附体系与对应洁净/缺陷表面必须保持同一 slab、超胞和真空。
- 若涉及 CO 与表面氧反应，结构准备阶段应输出每个静态构型，反应能或路径分析交给下游 workflow。

## 校验

每次输出 POSCAR 后运行：

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/validate_structure.py \
  --input POSCAR
```

对 CO/金属 slab 吸附结构，额外检查 adsorbate-slab 最近距离：

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/validate_structure.py \
  --input POSCAR --slab-elements Pt --adsorbate-elements C O \
  --min-adsorbate-slab-distance 1.4
```

吸附体系建议使用：

```bash
cd "<Repository root>" && python .claude/skills/structure/scripts/validate_structure.py \
  --input POSCAR_Pt111_CO_fcc_upright --min-distance 0.75 --min-vacuum 10
```

校验重点：

- 文件能被 pymatgen 读取。
- 化学式、原子数、元素种类符合预期。
- 最小原子间距没有明显重叠。
- slab 的 z 方向真空足够。
- 对吸附结构，吸附物没有嵌入 slab 或远离表面到不合理位置。

详细规则见 `references/validation_rules.md`。

## 汇报格式

结构生成后向用户汇报：

- 生成了哪些 POSCAR。
- 每个结构的化学式、原子数、用途。
- 使用的来源或构建方法。
- 关键几何参数：slab 层数、真空、超胞、吸附位点、高度、取向。
- 是否通过校验。
- 建议下一步使用哪个 skill。
