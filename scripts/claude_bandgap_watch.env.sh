#!/usr/bin/env bash

# 迁移到新服务器时，优先修改这个文件。
# Claude 版 watcher 主逻辑会在启动时自动 source 这里的变量。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ENV_FILE="${PROJECT_ENV_FILE:-$REPO_ROOT/.env}"

if [[ -f "$PROJECT_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PROJECT_ENV_FILE"
fi

# 非交互 shell 启动 watcher 时，主动从交互式 bash 中继承已配置的 API 环境变量。
if [[ -z "${GLM_API_KEY:-}" && -z "${ANTHROPIC_API_KEY:-}" ]] && command -v bash >/dev/null 2>&1; then
  _glm_api_key_from_bashrc="$(bash -ic 'printf "%s" "${GLM_API_KEY:-}"' 2>/dev/null || true)"
  _anthropic_api_key_from_bashrc="$(bash -ic 'printf "%s" "${ANTHROPIC_API_KEY:-}"' 2>/dev/null || true)"
  if [[ -n "$_glm_api_key_from_bashrc" ]]; then
    export GLM_API_KEY="$_glm_api_key_from_bashrc"
  fi
  if [[ -n "$_anthropic_api_key_from_bashrc" ]]; then
    export ANTHROPIC_API_KEY="$_anthropic_api_key_from_bashrc"
  fi
  unset _glm_api_key_from_bashrc _anthropic_api_key_from_bashrc
fi

# newvaspagent 数据根目录
export BG_DATA_ROOT="${BG_DATA_ROOT:-/mnt/data_x3/xiazeyu/newvaspagent/data/bandgap}"

# vaspagent / watcher 运行环境
export VASP_AGENT_PYTHON="${VASP_AGENT_PYTHON:-/data/xiazeyu/conda/envs/claude/bin/python}"
export VASP_AGENT_CONDA_SH="${VASP_AGENT_CONDA_SH:-/data/xiazeyu/conda/etc/profile.d/conda.sh}"
export VASP_AGENT_CONDA_ENV="${VASP_AGENT_CONDA_ENV:-claude}"
export CLAUDE_CLI="${CLAUDE_CLI:-$(command -v claude || true)}"
export CLAUDE_MODEL="${CLAUDE_MODEL:-glm-5.1}"

# Claude Code 走 Anthropic 协议时所需的上游配置。
# 若当前 shell 已提前 export 了这些变量，这里不会覆盖。
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.sfkey.cn}"
export GLM_API_KEY="${GLM_API_KEY:-${UPSTREAM_API_KEY:-}}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-${GLM_API_KEY:-${UPSTREAM_API_KEY:-}}}"

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
export BG_CLAUDE_PRINT_TIMEOUT="${BG_CLAUDE_PRINT_TIMEOUT:-300}"

# supervisor 会话名
export BG_WATCH_SUPERVISOR_SESSION="${BG_WATCH_SUPERVISOR_SESSION:-bgclaudewatch}"

# 串行任务列表
export BG_TASK_DIRS="${BG_TASK_DIRS:-bg_PbS bg_ZnS}"
