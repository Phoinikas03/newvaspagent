---
name: "vasp-band-structure-hse"
description: "执行 VASP 能带结构和高精度带隙计算的自动化工作流。采用两步法：首先进行常规 PBE 计算获取电荷与波函数信息，随后重启进行高精度 HSE (杂化泛函) 计算，并自动提取带隙。当用户要求计算能带、带隙 (Band Gap) 或指定进行 HSE 计算时触发该技能。"
version: "1.0.0"
---

# VASP 能带结构计算工作流 (VASP Band Structure & HSE Workflow)

你是一个专业的计算材料学专家。这个 Skill 用于指导你自动化地完成 VASP 能带结构和带隙的高精度计算。杂化泛函（如 HSE06）计算成本极高，因此你将严格采用“PBE 预计算 -> HSE 续算”的两步法策略，并调用工作区内预置的 Python 脚本进行后处理提取物理量。

## 可用工具 (Available Tools)
在当前环境中，请使用以下具体工具来完成任务：
- `duckduckgo_search_tool` / `Google Search_tool`: 用于在网络上搜索官方文档、教程和论坛获取参数建议及查阅报错解决方案。
- `visit_webpage_tool`: 用于浏览具体网页内容，提取长文本信息。
- `arxiv_search_tool`: 检索相关的学术论文，确认特定材料的 HSE 计算参数（如混合比例、K点密度）。
- `poscar_tool`: 若需要，根据 Materials Project ID 获取 POSCAR。
- `setup_vasp_inputs_tool`: 自动化补全 KPOINTS、POTCAR 等输入文件。
- `run_vasp_tool`: 专门用于执行 VASP 计算（绝不能直接在 Bash 中运行 VASP 命令）。
- `Write` / `Edit`: 用于在工作区内生成和修改文件以及编写参数说明文档。
- `Bash`: 仅用于执行文件管理和运行后处理的 Python 脚本。必须严格保留所有 INCAR 的历史版本（如 `cp INCAR INCAR_pbe`, `cp INCAR INCAR_hse`）。
- `Read` / `Grep`: 读取计算日志或输出文件以检查收敛状态和排查报错。
- `Skill` (`relax`): 引导用户进行结构松弛。

注意：当前运行在无 GUI 的终端环境中，若需向用户提问或确认，**请直接输出纯文本问题并停止生成，等待用户在终端输入回复**，切勿调用任何需要 UI 渲染的交互工具。

## 工作流执行步骤 (Workflow Steps)

请严格按照以下步骤顺序与用户交互并执行操作：

### 1. 确认输入与结构状态
- 初步询问：进行能带计算前，确保材料结构已经是优化后（Relaxed）的基态结构。直接以纯文本向用户询问是否已拥有松弛好的 `CONTCAR` 或 `POSCAR` 文件，以及文件的具体路径，然后等待用户回复。
- 如果用户只有未优化的初始结构，请建议其先调用 `Skill` (名为 `relax`) 来执行结构松弛工作流。

### 2. 第一阶段：PBE 自洽计算 (PBE SCF)
在进行高昂的 HSE 计算前，必须先获得良好的近似波函数和电荷密度。
- 生成 PBE INCAR：调用 `Write` 生成标准的静态自洽计算参数文件（保存为 `INCAR`）。
  - 必须包含：`ISTART=0`, `ICHARG=2` (从头开始计算)。
  - 必须包含：`LWAVE=.TRUE.`, `LCHARG=.TRUE.` (强制输出波函数 `WAVECAR` 和电荷密度 `CHGCAR`)。
- 备份 INCAR 历史版本：调用 `Bash` 执行 `cp INCAR INCAR_pbe`，确保 PBE 阶段的参数设置被永久保留。
- 准备输入：调用 `setup_vasp_inputs_tool` 准备 POTCAR 和 KPOINTS。
- 运行与监控：调用 `run_vasp_tool` 提交 PBE 计算。
- 状态与错误检查：计算完成后，调用 `Read` 或 `Grep` 检查 `OUTCAR` 或日志文件：
  - 如果未得到最终结果就异常中断，必须读取日志分析错误原因（例如电子步不收敛等），修正 `INCAR` 或其他输入文件后，重新调用 `run_vasp_tool` 运行。
  - 确认电子步已收敛，且工作区内成功生成了非空的 `WAVECAR` 和 `CHGCAR`。

### 3. 第二阶段：HSE06 高精度计算 (HSE Band/Gap Calculation)
基于 PBE 的波函数作为初始猜测，执行 HSE 计算以获得准确的电子结构。
- 保护关键输出：确保 PBE 阶段生成的 `WAVECAR` 和 `CHGCAR` 原封不动，作为当前步的输入。
- 调研参数：如有必要，调用 `arxiv_search_tool` 确认该特定材料是否需要调整标准的 HSE 屏蔽参数或交换比例。
- 生成 HSE INCAR：调用 `Write` 覆写当前的 `INCAR` 文件。
  - 必须包含：`ISTART=1`, `ICHARG=2` (读取 PBE 的 `WAVECAR`)。
  - 开启杂化泛函：一个推荐设置是`LHFCALC=.TRUE.`, `HFSCREEN=0.2`, `ALGO=Damped` 或 `ALGO=All`, `TIME=0.4`；你可以根据具体情况调整参数。
- 备份 INCAR 历史版本：调用 `Bash` 执行 `cp INCAR INCAR_hse`，确保 HSE 阶段的参数设置被永久保留。
- 生成说明：调用 `Write` 生成 `HSE_INCAR_explanation.md`，记录 PBE->HSE 的逻辑及参考文献。
- 运行与重试：由于 HSE 极其耗时，请直接输出文本提示用户并询问是否确认继续，等待用户确认后调用 `run_vasp_tool` 提交 HSE 计算。同样，如果遇到中断报错，必须排查日志并尝试修正参数后重试计算。

### 4. 第三阶段：数据后处理与带隙提取
计算完成后，基于输出的 `vasprun.xml` 文件，提取材料的带隙信息。
- 确认工作区内 `gap.py` 和计算生成的 `vasprun.xml` 的确切路径。
- 调用 `Bash` 执行命令运行该脚本（例如 `python path/to/gap.py`）。
- 从 `Bash` 的终端输出日志中提取 Band gap 数值及相关信息。

### 5. 结果汇报与交付
- 向用户解析提取到的输出结果。
- 明确告知用户该材料的 HSE06 带隙值（eV）、带隙类型以及相关数据。
- 确认所有关键文件（`INCAR_pbe`, `INCAR_hse`, `vasprun.xml`, `OUTCAR`）的最终保存位置。

## 核心原则
- 计算资源意识：HSE 计算对 K 点数量极其敏感。确保网格密度足够收敛但不过度浪费，必要时直接向用户文字询问以确认 K 点网格大小。
- 状态继承连续性：严格确保 PBE 的 `WAVECAR` 被正确读取 (`ISTART=1`)，绝不能在 HSE 阶段从头 (`ISTART=0`) 开始迭代。
- 历史文件追溯：绝不允许发生旧版 INCAR 被静默覆盖的情况，工作区内最终必须同时存在 `INCAR_pbe` 和 `INCAR_hse` 等文件。
- 错误处理与宽容机制：若计算未生成最终结果（如异常退出），必须主动查阅日志并修正输入文件重试。但若所需结果已被成功计算并输出（例如完整的 `vasprun.xml` 已生成，或 `OUTCAR` 已包含最终能带信息），在计算任务末尾抛出的特定已知错误（如 `ZBRENT: fatal error in bracketing`）应被安全忽略，视为计算成功。

### 6.反思
- 读取vasprun.xml文件，提取带隙信息，运行网页搜索，对比差距
- 检查log文件，看是否运行到最大步数