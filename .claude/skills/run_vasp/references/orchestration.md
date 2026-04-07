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