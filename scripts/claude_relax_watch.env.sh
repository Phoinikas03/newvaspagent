#!/usr/bin/env bash

# 迁移到新服务器时，优先修改这个文件。
# Claude 版 relax watcher 主逻辑会在启动时自动 source 这里的变量。

if [[ -z "${GLM_API_KEY:-}" && -z "${ANTHROPIC_API_KEY:-}" ]] && command -v bash >/dev/null 2>&1; then
  _claude_bootstrap='
    if declare -F claude_on >/dev/null 2>&1; then
      claude_on >/dev/null 2>&1 || true
    fi
    printf "%s\n%s\n%s" "${GLM_API_KEY:-}" "${ANTHROPIC_API_KEY:-}" "${ANTHROPIC_BASE_URL:-}"
  '
  mapfile -t _claude_env_from_bashrc < <(bash -ic "$_claude_bootstrap" 2>/dev/null || true)
  _glm_api_key_from_bashrc="${_claude_env_from_bashrc[0]:-}"
  _anthropic_api_key_from_bashrc="${_claude_env_from_bashrc[1]:-}"
  _anthropic_base_url_from_bashrc="${_claude_env_from_bashrc[2]:-}"
  if [[ -n "$_glm_api_key_from_bashrc" ]]; then
    export GLM_API_KEY="$_glm_api_key_from_bashrc"
  fi
  if [[ -n "$_anthropic_api_key_from_bashrc" ]]; then
    export ANTHROPIC_API_KEY="$_anthropic_api_key_from_bashrc"
  fi
  if [[ -n "$_anthropic_base_url_from_bashrc" ]]; then
    export ANTHROPIC_BASE_URL="$_anthropic_base_url_from_bashrc"
  fi
  unset _claude_bootstrap
  unset _claude_env_from_bashrc
  unset _glm_api_key_from_bashrc _anthropic_api_key_from_bashrc _anthropic_base_url_from_bashrc
fi

_rx_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# newvaspagent 数据根目录
export RX_DATA_ROOT="${RX_DATA_ROOT:-${_rx_repo}/data/relax}"

# vaspagent / watcher 运行环境
export VASP_AGENT_PYTHON="${VASP_AGENT_PYTHON:-/data/xiazeyu/conda/envs/claude/bin/python}"
export VASP_AGENT_CONDA_SH="${VASP_AGENT_CONDA_SH:-/data/xiazeyu/conda/etc/profile.d/conda.sh}"
export VASP_AGENT_CONDA_ENV="${VASP_AGENT_CONDA_ENV:-claude}"
export CLAUDE_CLI="${CLAUDE_CLI:-$(command -v claude || true)}"
export CLAUDE_MODEL="${CLAUDE_MODEL:-glm-5.1}"

# Claude Code 走 Anthropic 协议时所需的上游配置。
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.sfkey.cn}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-${GLM_API_KEY:-}}"

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
export RX_TMUX_SESSION="${RX_TMUX_SESSION:-rxvasp}"
export RX_WATCH_INTERVAL="${RX_WATCH_INTERVAL:-45}"
export RX_WATCH_COUNT="${RX_WATCH_COUNT:-4000}"
export RX_WATCH_RESTART_DELAY="${RX_WATCH_RESTART_DELAY:-5}"
export RX_CLI_READY_TIMEOUT="${RX_CLI_READY_TIMEOUT:-120}"
export RX_CLAUDE_PRINT_TIMEOUT="${RX_CLAUDE_PRINT_TIMEOUT:-300}"

# supervisor 会话名
export RX_WATCH_SUPERVISOR_SESSION="${RX_WATCH_SUPERVISOR_SESSION:-rxclaudewatch}"

# 串行任务列表
export RX_TASK_DIRS="${RX_TASK_DIRS:-rx_Ni rx_Sb2Te3 rx_SiO2 rx_SnSe rx_Sr2RuO4 rx_TePb rx_Ti rx_TiC rx_TiPbO3 rx_Zn}"

unset _rx_repo
