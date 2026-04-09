---
name: supercell
description: 执行晶体结构的线性扩胞（Supercell Generation）。当用户要求“扩大 POSCAR”、“构建超胞”或指定扩胞倍数（如 2x2x2）时触发。使用 pymatgen 进行处理，并在执行前向用户确认原子数变化。
---

# Supercell Generation Skill

此 Skill 用于将现有的 `POSCAR` 文件按照指定的倍数进行线性扩胞。

## 触发条件
- 用户提到“扩胞”、“构建超胞”、“扩大结构”。
- 用户给出具体的扩胞倍数，如 "3x3x1", "2*2*2", "把 a, b 方向扩大 2 倍" 等。

## 执行逻辑

1. **解析需求**：从用户指令中提取 $n_1, n_2, n_3$ 三个方向的扩胞倍数。如果用户只说“扩大 2 倍”，默认指 $2\times2\times2$。
2. **检查环境**：确保当前目录下存在 `POSCAR`。
3. **预计算与确认**：
   - 使用 `scripts/make_supercell.py --info` 获取扩胞前后的信息（原子总数变化）。
   - **必须**向用户汇报：“准备将结构从 N 个原子扩展到 M 个原子（倍数：$n_1 \times n_2 \times n_3$），是否继续？”
4. **执行扩胞**：用户确认后，运行 `scripts/make_supercell.py`。
5. **结果处理**：生成 `POSCAR_supercell` 文件，并提醒用户检查。不要自动覆盖原始 `POSCAR`，除非用户明确要求。

## 注意事项
- 扩胞后原子数过多（如超过 500 个）时，应特别提醒用户计算成本会显著增加。
- 保持原子标签和坐标系的完整性。

## 执行方式（与系统 ITERATIVE EXECUTION RULE 一致）

本 skill 仅通过 `scripts/make_supercell.py` 生成结构。若用户需对**多种**超胞方案或多个输出结构**分别**跑 VASP，须**逐目录**提交并在每步核查；**禁止**用 `for` 或 monolithic Bash 一次提交全部相关 VASP。实际计算一律走 Skill `run_vasp`（含 Step 2–3 的环境探针与 **STRICT HARDWARE ALIGNMENT**），并遵守其 Step 4：对 `vasp_runner.py --dirs` **分批**调用、在中间读 OUTCAR/日志后再继续，不得单次把全部目录无核查地排队跑完。

## 核心原则

- **禁止以扩胞为借口批量跑 VASP**：结构准备可一次完成；一旦进入 `mpirun` / `vasp_runner`，仍须迭代执行，与 `relax`、`lattice_constant` 等 skill 口径一致。
