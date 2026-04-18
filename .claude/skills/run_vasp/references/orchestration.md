# Agent 调度策略与防灾指南

## 1. 登录节点禁忌 (The Login Node Taboo)
如果在 `probe_env.py` 中发现 `"is_login_node": true`：
- **绝对禁止** 使用 `--mode local` 调用 `mpirun`。
- 必须强制引导用户使用 Slurm/PBS 提交作业，或者使用 `salloc` 申请交互式节点。

## 2. 内存防爆 (OOM Prevention)
在胖节点高通量场景中（如 256 核），不要简单地把核心数除以任务数。
- 如果用户体系大（如数百个原子），每个任务可能需要 64GB 内存。
- 作为 Agent，如果你怀疑内存不足，提醒用户：“由于是多任务并发，请确保节点总内存足够，否则会导致 Segmentation Fault。”

## 3. GPU 绑定逻辑解释
`vasp_runner.py` 中的 `--gpu-per-task` 实现了显存层面的物理隔离。例如传入 `--gpu-per-task 1`，它会自动为任务0分配 `CUDA_VISIBLE_DEVICES=0`，为任务1分配 `CUDA_VISIBLE_DEVICES=1`。这比依赖系统自动分配要安全得多。

**与主 SKILL 对齐**：一般 **GPU 版 VASP** 下 **1 MPI rank ↔ 1 GPU**；单卡单任务用 `mpirun -np 1`，可执行文件可为 **`vasp_gpu`**，也可为站点上的 **GPU 版 `vasp_std`**（如模块/路径中的 `vasp_std/gpu` 等）。完整规则见 `SKILL.md`「核心执行准则 §1」。

**启动前门控（`vasp_runner.py`，本地且 `--gpu-per-task>0`）**：通过 `nvidia-smi` 查询每卡 **空闲显存** 与 **GPU 计算利用率**。默认要求 **memory.free ≥ 约 10 GiB**（`--min-gpu-free-mib`，传 `0` 关闭），且 **utilization.gpu 严格小于 10%**（`--max-gpu-util-percent`，传 `0` 关闭）。灵活队列会在两条件同时满足后再绑定 GPU；不满足则轮询等待或超时。

## 4. 可执行依赖探测（mpirun / VASP）
`probe_env.py` 输出的 `dependencies` 字段包含：
- `mpirun_found`
- `vasp_std_found`
- `vasp_gpu_found`

**策略阶段**：若计划本地运行而对应项为 `false`，必须在策略中说明，并让用户确认 `env_script`（如 `template/env_local.sh`）中的 `module load` / `PATH`，**禁止**在未解决前调用 `vasp_runner.py --mode local` 或 `quick_test.py`。

**Slurm**：登录节点上三项均可为 `false`；应在作业脚本内 `source` 用户提供的 env，并在策略中明确「计算节点上加载模块」，避免在登录节点执行 `mpirun`。

`vasp_runner.py` 与 `quick_test.py` 在本地模式下会在执行前再次校验（若传入 `--env-script` 则在 `source` 后校验），失败时打印 `ERROR:` 并以非零码退出，供 Agent 与全局 `command not found` 规则联动。

## 5. 硬性分叉（CPU+GPU 共存 / 调度器）
与项目 **system_prompt** 中 **STRICT HARDWARE ALIGNMENT** 一致：
- **GPU 与 CPU 同时可用**：不得默认纯 CPU 多核方案；须先问用户要 GPU 还是仅 CPU、用几张 GPU。GPU 入口可能是 `vasp_gpu` 或 GPU 版 `vasp_std`（见主 SKILL §1）。
- **已检测到 Slurm/PBS**：不得用本地 `mpirun` 代替提交作业；须先问 partition/queue、节点数、时限等再写脚本。