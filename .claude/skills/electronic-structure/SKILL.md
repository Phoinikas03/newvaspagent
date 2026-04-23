---
name: "vasp-electronic-structure"
description: "执行 VASP 电子结构工作流：静态 SCF、带结构、DOS，以及高精度 HSE 带隙。它是在原 bandgap skill 基础上的升级版，统一收纳 PBE→HSE 带隙、band structure、DOS 等电子结构任务。真正运行前必须经过 run_vasp；涉及 GPU、KPAR、NCORE、NPAR 时必须先经过 performance。"
version: "1.0.0"
---

# VASP Electronic Structure Workflow

这个 skill 统一处理以下任务：

- 静态单点电子结构基准
- Band structure
- Density of states (DOS / PDOS)
- PBE 带隙
- HSE 高精度带隙

它是对旧 `bandgap` workflow 的扩展，而不是完全替代运行规则。原来关于 `PBE -> HSE`、`WAVECAR` 连续性、HSE 启动前单独确认、GPU 卡数确认等要求，仍然保留。

## 目录结构

```text
electronic-structure/
├── SKILL.md
├── scripts/
│   └── gap.py
├── references/
│   ├── hse_params.md
│   └── troubleshooting.md
└── templates/
    ├── INCAR_pbe_scf
    └── INCAR_hse
```

## 相关技能

- `run_vasp`：正式运行入口，必须使用
- `performance`：只要用户提到 GPU、`KPAR`、`NCORE`、`NPAR` 或希望按硬件优化时，必须先用
- `convergence`：正式电子结构对比前建议先做 `ENCUT/KSPACING` 收敛
- `relax`：若结构还未优化，优先先松弛
- `vasp_error`：出错、卡住、超时时的诊断与恢复

## 工作流选择

### A. 静态 SCF

适用于：
- 最终总能量
- 后续 DOS / band structure / HSE 的前置电荷与波函数

步骤：
1. 确认结构来源
2. 视需要先做 `convergence`
3. 读取并写入 `templates/INCAR_pbe_scf`
4. 生成输入文件
5. 通过 `run_vasp` 的 `vasp_runner.py` 提交
6. 用 `run_vasp/scripts/check_convergence.py` 检查
7. 若失败、未收敛或疑似卡住，优先转给 `vasp_error`

### B. Band Structure / DOS

典型两步法：
1. 先做静态 SCF，生成稳定的 `CHGCAR` / `WAVECAR`
2. 再做非自洽 band structure 或 DOS

要求：
- 非自洽阶段不得和前一步的核心口径混乱
- 做投影时开启 `LORBIT`
- 线模式 band structure 需用户或上游明确提供 / 生成高对称路径 KPOINTS
- 若非自洽阶段异常退出或后处理文件不完整，优先用 `vasp_error` 判断是否是输入问题、收敛问题，还是仅后处理不完整

### C. HSE 高精度带隙

严格采用：
1. PBE SCF
2. PBE 收敛检查
3. 准备 HSE 输入
4. **单独**向用户确认是否继续 HSE
5. 若有 GPU，**单独问清 GPU 卡数**
6. 再通过 `run_vasp` 提交 HSE
7. 用 `scripts/gap.py` 提取带隙

## 失败与恢复

无论是静态 SCF、band structure、DOS，还是 HSE，只要出现以下任一情况，都应先转给 `vasp_error`：

- `vasp_runner.py` 非零退出
- `run_vasp/scripts/check_convergence.py` 返回 `failed` / `unconverged` / `incomplete_postprocess`
- 日志、`OUTCAR`、`OSZICAR` 长时间没有新输出
- GPU / MPI / 内存报错后，需要判断是否应先停旧任务

处理顺序应为：

1. 先 `Read references/troubleshooting.md`
2. 结合当前阶段（PBE / HSE / DOS / band structure）检查最直接的本地排障建议
3. 若仍需统一判断“是否继续等待、是否要 terminate、如何修改后重跑”，再调用 `vasp_error`

推荐调用：

```bash
cd "<repo_root>" && python .claude/skills/vasp_error/scripts/analyze_error.py --work-dir "<当前任务目录>"
```

根据 `vasp_error` 的输出来决定：

- 是否继续等待
- 是否修改 `NELM` / `ALGO` / `ISMEAR` / `SIGMA` / HSE 参数
- 是否建议先 terminate 旧 run 再重新提交

若 `vasp_error` 建议先停旧 run，必须先向用户说明证据、拟修改项和新的 runner 命令。只有在用户明确同意后，才允许：

```bash
cd "<repo_root>" && python .claude/skills/run_vasp/scripts/terminate.py --work-dir "<当前任务目录>" --reason "<停止原因>"
```

**禁止**在旧 run 可能仍活着时，向同一目录补开第二个活跃的 PBE / HSE / DOS / band structure 任务。

## HSE 强制规则

1. **HSE 启动前必须单独确认**
   在 PBE 已收敛、HSE 输入文件已准备好之后，必须单独停下来询问用户是否继续。

2. **有 GPU 时必须问清卡数**
   用户只说“继续”但没说 GPU 张数时，不能默认 1 卡或多卡。

3. **WAVECAR 连续性**
   HSE 热启动要求前后阶段 `ENCUT` 和 K 点口径一致；若不一致，不能继续拿旧 `WAVECAR` 硬续。

4. **出错先诊断再决定是否停**
   若 HSE 因 GPU/MPI/内存问题异常，优先用 `vasp_error` 看是否应先 terminate，再修改参数并重新提交。

## 推荐后处理

带隙提取：

```bash
cd "<repo_root>" && python .claude/skills/electronic-structure/scripts/gap.py "<vasprun.xml>"
```

## 禁止事项

- 不得直接手写正式 `mpirun ... vasp_std/vasp_gpu`
- 不得在同一目录里补开第二个活跃 VASP 进程
- 不得在未获用户确认时直接启动 HSE
- 不得在用户要求按硬件优化时跳过 `performance`
- 不得跳过 `vasp_error`，直接对失败或疑似卡住的旧 run 做模糊终止或盲目重跑

## 结果汇报

至少包括：

- 采用的电子结构工作流类型
- 是否完成 PBE / HSE / DOS / band structure
- 关键文件位置
- 若是带隙任务，报告带隙值、直接/间接、跃迁路径
