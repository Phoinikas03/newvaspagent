#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE_DEFAULT="$REPO/scripts/codex_bandgap_watch.env.sh"
ENV_FILE="${BG_WATCH_ENV_FILE:-$ENV_FILE_DEFAULT}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

SESSION="${BG_WATCH_SUPERVISOR_SESSION:-bgwatch}"
LOCK_DIR="${BG_WATCH_LOCK_DIR:-$REPO/runs/codex_bandgap_watch.lock}"
LOCK_PID_FILE="$LOCK_DIR/pid"

if ! command -v tmux >/dev/null 2>&1; then
  echo "未找到 tmux，请先安装或加入 PATH。" >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux kill-session -t "$SESSION"
  echo "已停止 watch supervisor: tmux session=$SESSION"
else
  echo "watch supervisor 未运行: tmux session=$SESSION"
fi

if [[ -f "$LOCK_PID_FILE" ]]; then
  old_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "发现 watcher 进程仍存在，尝试定点终止 pid=$old_pid"
    kill "$old_pid" 2>/dev/null || true
  fi
fi

rm -rf "$LOCK_DIR" 2>/dev/null || true
echo "已清理 watcher 锁: $LOCK_DIR"
