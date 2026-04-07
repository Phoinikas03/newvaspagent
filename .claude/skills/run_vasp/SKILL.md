# Skill: Run VASP (Intelligent Orchestrator)

## 核心目标
作为高级计算科学助理，你的职责是安全、高效地编排 VASP 任务。在执行任何计算前，你必须感知所处环境，绝不能在未确认资源的情况下盲目执行 `mpirun`。

## 工作流 (Workflow)

### Step 1: 意图识别 (Intent Recognition)
- 询问用户或分析 Prompt：这是正式的生产计算（Production），还是只是为了测试输入文件是否合法的快速验证（Pre-flight / Quick Test）？
- **如果属于场景 5（快速试错）**：直接调用 `scripts/quick_test.py`。
- **如果是生产计算**：进入 Step 2。

### Step 2: 环境侦察 (Environment Probing)
- 运行探针脚本：`python .claude/skills/run_vasp/scripts/probe_env.py`
- 分析 JSON 输出结果（CPU 核心数、GPU 数量、是否存在 Slurm 调度器、是否为登录节点）。

### Step 3: 策略制定 (Strategy formulation)
根据探针结果和待计算的目录数量，向用户推荐以下策略之一：
- **场景 1 (胖节点裸机多任务)**：无 Slurm，资源充足。推荐使用 `vasp_runner.py` 的 `--mode local`，并为每个目录分配合适的 `--np`（例如 256核跑4个任务，每个 `--np 64`）。
- **场景 2 (HPC 集群)**：存在 Slurm，且处于登录节点。**严禁执行本地 mpirun**。推荐使用 `--mode slurm` 生成并提交作业。
- **场景 3 (GPU 工作站)**：存在 GPU。若有多个任务，建议配置 `--gpu-per-task 1` 实现一卡一任务隔离。

### Step 4: 执行与追踪 (Execution & Tracking)
- 与用户确认策略后，调用 `scripts/vasp_runner.py`。
- 告知用户查看日志的路径，若为 Slurm 作业，使用 `squeue -u $USER` 帮用户追踪排队状态。