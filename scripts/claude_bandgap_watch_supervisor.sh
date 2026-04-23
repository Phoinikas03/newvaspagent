#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE_DEFAULT="$REPO/scripts/claude_bandgap_watch.env.sh"
ENV_FILE="${BG_WATCH_ENV_FILE:-$ENV_FILE_DEFAULT}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

RUNS="$REPO/runs"
LOG="${BG_WATCH_SUPERVISOR_LOG:-$RUNS/claude_bandgap_watch.supervisor.log}"
WATCH_SCRIPT="$REPO/scripts/claude_bandgap_watch.sh"
RESTART_DELAY="${BG_WATCH_RESTART_DELAY:-5}"

mkdir -p "$RUNS"

log() {
  echo "$*" | tee -a "$LOG"
}

log "==== watch supervisor 开始 $(date -Is) pid=$$ ===="

while true; do
  log "[supervisor] 启动 watcher $(date -Is)"
  set +e
  bash "$WATCH_SCRIPT" >>"$LOG" 2>&1
  ec=$?
  set -e
  log "[supervisor] watcher 退出 exit=$ec $(date -Is)"
  if [[ "$ec" -eq 0 ]]; then
    log "[supervisor] watcher 正常退出，不再自动重启"
    break
  fi
  sleep "$RESTART_DELAY"
done
