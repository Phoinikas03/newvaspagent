---
name: "vasp-error-recovery"
description: "在 VASP 计算失败、未收敛、长时间无新输出、GPU/MPI 异常或需要判断是否应先停止当前 run 再修改参数重跑时触发。读取 run_vasp 的 state 文件、OUTCAR、OSZICAR、主日志与 check_convergence 结果，给出结构化排障建议，并在用户确认后才允许调用 terminate.py。"
version: "1.0.0"
---

# VASP Error Recovery

这个 skill 负责在 VASP 出错、疑似卡住或超时后，先做**证据化诊断**，再给出**修改建议**与**是否应停止当前任务**的判断。

它不是运行入口。真正启动/重跑 VASP 仍应交给 `run_vasp`。

## 何时使用

出现下列任一情形时，应使用本 skill：

- `run_vasp/scripts/check_convergence.py` 返回 `failed`、`unconverged`、`incomplete_postprocess`
- `vasp_runner.py` 返回非零退出码
- GPU/MPI/内存报错后，需要决定是否应先停止旧任务
- 运行时间过长，且日志、`OUTCAR`、`OSZICAR` 长时间没有新输出
- 用户明确说“报错了”“卡住了”“超时了”“要不要停掉重跑”

## 可用资产

```text
vasp_error/
├── SKILL.md
├── references/
│   └── troubleshooting.md
└── scripts/
    └── analyze_error.py
```

## 核心原则

1. **先诊断，后动作**
   在真正停止进程或修改输入前，先读取 state、日志与 `check_convergence` 结果。

2. **先用调用方的本地 troubleshooting，再用本 skill 做统一诊断**
   若上游 workflow 自己带有 `references/troubleshooting.md` 或等价本地规则，调用方应先阅读它，先消化该任务专属的排障建议；当仍需统一判断“是否应 terminate 当前 run、是否只是 stalled、如何组织重跑方案”时，再进入本 skill。

3. **只处理有证据归属的任务**
   若当前任务没有 `run_vasp` 生成的 `.vasp_run_state.json`，或无法证明进程归属，不得擅自终止。

4. **不自动重跑**
   本 skill 只输出建议，不在未得到用户确认的情况下自动停止或重提任务。

5. **终止必须经用户确认**
   若建议停止当前任务，必须明确告诉用户：
   - 为什么建议停
   - 当前 run 是否仍在
   - 停止后准备如何改
   - 新的 `vasp_runner.py` 命令将是什么

## 标准流程

### 1. 收集证据

调用本 skill 之前，若上游 skill 有自己的本地排障文档，应先读取它：

- 例如 `relax/references/troubleshooting.md`
- 或 `electronic-structure/references/troubleshooting.md`

然后再进入本 skill 做统一诊断。

优先读取：

- 当前目录的 `.vasp_run_state.json`
- `OUTCAR`
- `OSZICAR`
- 当前主日志（优先使用 state 中记录的 `log_path`）
- `run_vasp/scripts/check_convergence.py` 输出

建议直接运行：

```bash
cd "<repo_root>" && python .claude/skills/vasp_error/scripts/analyze_error.py --work-dir "<task_dir>"
```

### 2. 匹配问题类型

结合 `references/troubleshooting.md`，优先判断是否属于：

- 电子步不收敛
- 离子步不收敛
- `ZBRENT`
- 内存/LAPACK 错误
- `WAVECAR` 不匹配
- `POTCAR` 顺序或用户指定赝势变体未同步的问题
- 晶胞异常变化
- HSE 极慢或卡住
- 长时间无新输出的 stalled run

### 3. 输出建议

至少向用户说明：

- 你识别到的问题类型
- 依据是什么
- 建议改哪些参数或输入
- 是否建议先停止当前任务
- 若重跑，是否必须先终止旧任务

### 4. 若用户同意停止

只有在以下条件同时满足时，才允许调用：

```bash
cd "<repo_root>" && python .claude/skills/run_vasp/scripts/terminate.py --work-dir "<task_dir>" --reason "<reason>"
```

若这是旧的手写启动任务且没有 `.vasp_run_state.json`，必须先只做候选检查：

```bash
cd "<repo_root>" && python .claude/skills/run_vasp/scripts/terminate.py --work-dir "<task_dir>" --allow-cwd-scan --dry-run
```

只有当 dry-run 输出中的每个候选 PID 都显示 cwd 精确等于 `<task_dir>` 时，才允许在用户同意后去掉 `--dry-run` 执行。不要改用 `pkill -f` 或任何命令行模式匹配。

条件：

- 当前 run 的归属证据明确
- 用户已明确同意停止
- 你已经说明停止后要怎么改和如何重跑

### 5. 重跑

停止后，回到 `run_vasp` 流程：

- 修改输入
- 若需要重新生成 `POTCAR`，必须调用 `setup_vasp_inputs`；若用户原先指定过赝势变体，必须在同一次工具调用中传入相同的 `potcar_overrides` JSON object（如 `{"Cr": "Cr_pv"}`），不得用 Bash/Python 手工生成、拼接或复制 `POTCAR`
- 向用户展示新的 `vasp_runner.py` 命令
- 再次取得用户确认
- 重新提交

## 禁止事项

- 不得用 `pkill`、`killall`、`pkill -f vasp_std`、`pkill -f "vasp_gpu.*<dir>"` 之类模糊命令；`pkill -f` 可能误杀正在执行命令的 shell/消息读取进程
- 不得在旧 run 可能仍活着时，向同一目录再补开一个新的 `mpirun`
- 不得只看到 “fatal error” 就直接认定必须重算
- 不得在未获用户同意时自动 terminate + rerun
- 不得绕过 `setup_vasp_inputs` 手工修复 `POTCAR`；用户指定赝势变体时，错误恢复和重跑必须继续使用同一份 `potcar_overrides`
