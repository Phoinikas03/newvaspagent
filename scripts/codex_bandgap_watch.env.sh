#!/usr/bin/env bash

# 迁移到新服务器时，优先修改这个文件。
# 主逻辑脚本会在启动时自动 source 这里的变量。

# newvaspagent 数据根目录
export BG_DATA_ROOT="${BG_DATA_ROOT:-/home/xiazeyu21/newvaspagent/data/bandgap}"

# vaspagent / watcher 运行环境
export VASP_AGENT_PYTHON="${VASP_AGENT_PYTHON:-/gpfs/junlab/xiazeyu21/miniconda3/envs/vaspagent/bin/python}"
export VASP_AGENT_CONDA_SH="${VASP_AGENT_CONDA_SH:-/gpfs/junlab/xiazeyu21/miniconda3/etc/profile.d/conda.sh}"
export VASP_AGENT_CONDA_ENV="${VASP_AGENT_CONDA_ENV:-vaspagent}"
export CODEX_CLI="${CODEX_CLI:-$(command -v codex || ls -d "$HOME"/.vscode-server/extensions/openai.chatgpt-*/bin/linux-x86_64/codex 2>/dev/null | sort | tail -n 1)}"

# 网络代理
export HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7890}"
export HTTPS_PROXY="${HTTPS_PROXY:-$HTTP_PROXY}"
export ALL_PROXY="${ALL_PROXY:-socks5://127.0.0.1:7890}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1,.localdomain}"
export http_proxy="${http_proxy:-$HTTP_PROXY}"
export https_proxy="${https_proxy:-$HTTPS_PROXY}"
export all_proxy="${all_proxy:-$ALL_PROXY}"
export no_proxy="${no_proxy:-$NO_PROXY}"

# watcher 行为参数
export BG_TMUX_SESSION="${BG_TMUX_SESSION:-bgvasp}"
export BG_WATCH_INTERVAL="${BG_WATCH_INTERVAL:-45}"
export BG_WATCH_COUNT="${BG_WATCH_COUNT:-4000}"
export BG_WATCH_RESTART_DELAY="${BG_WATCH_RESTART_DELAY:-5}"
export BG_CLI_READY_TIMEOUT="${BG_CLI_READY_TIMEOUT:-120}"
export BG_CODEX_EXEC_TIMEOUT="${BG_CODEX_EXEC_TIMEOUT:-300}"

# supervisor 会话名
export BG_WATCH_SUPERVISOR_SESSION="${BG_WATCH_SUPERVISOR_SESSION:-bgwatch}"

# 串行任务列表
export BG_TASK_DIRS="${BG_TASK_DIRS:-bg_InP bg_InSe bg_MoS2 bg_PbS}"
