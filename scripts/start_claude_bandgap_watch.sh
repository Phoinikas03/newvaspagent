#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE_DEFAULT="$REPO/scripts/claude_bandgap_watch.env.sh"
ENV_FILE="${BG_WATCH_ENV_FILE:-$ENV_FILE_DEFAULT}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

SESSION="${BG_WATCH_SUPERVISOR_SESSION:-bgclaudewatch}"
SUPERVISOR_SCRIPT="$REPO/scripts/claude_bandgap_watch_supervisor.sh"

if ! command -v tmux >/dev/null 2>&1; then
  echo "未找到 tmux，请先安装或加入 PATH。" >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "watch supervisor 已在运行: tmux session=$SESSION"
  echo "可用以下命令查看："
  echo "tmux attach -t $SESSION"
  exit 0
fi

tmux new-session -d -s "$SESSION" "cd \"$REPO\" && bash \"$SUPERVISOR_SCRIPT\""

echo "watch supervisor 已启动: tmux session=$SESSION"
echo "查看 supervisor:"
echo "tmux attach -t $SESSION"
echo "查看 vaspagent:"
echo "tmux attach -t ${BG_TMUX_SESSION:-bgvasp}"
