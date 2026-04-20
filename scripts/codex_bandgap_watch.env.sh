#!/usr/bin/env bash

# 迁移到新服务器时，优先修改这个文件。
# 主逻辑脚本会在启动时自动 source 这里的变量。

# newvaspagent 数据根目录
export BG_DATA_ROOT="${BG_DATA_ROOT:-/mnt/data_x3/xiazeyu/newvaspagent/data/bandgap}"

# vaspagent / watcher 运行环境
export VASP_AGENT_PYTHON="${VASP_AGENT_PYTHON:-/data/xiazeyu/conda/envs/claude/bin/python}"
export VASP_AGENT_CONDA_SH="${VASP_AGENT_CONDA_SH:-/data/xiazeyu/conda/etc/profile.d/conda.sh}"
export CODEX_CLI="${CODEX_CLI:-codex}"

# watcher 行为参数
export BG_TMUX_SESSION="${BG_TMUX_SESSION:-bgvasp}"
export BG_WATCH_INTERVAL="${BG_WATCH_INTERVAL:-45}"
export BG_WATCH_COUNT="${BG_WATCH_COUNT:-4000}"
export BG_WATCH_RESTART_DELAY="${BG_WATCH_RESTART_DELAY:-5}"

# supervisor 会话名
export BG_WATCH_SUPERVISOR_SESSION="${BG_WATCH_SUPERVISOR_SESSION:-bgwatch}"

# 串行任务列表
export BG_TASK_DIRS="${BG_TASK_DIRS:-bg_CdTe bg_Cu2O bg_Ga2O3 bg_GaAs}"
