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
SUPERVISOR_SESSION="${BG_WATCH_SUPERVISOR_SESSION:-bgclaudewatch}"
AGENT_SESSION="${BG_TMUX_SESSION:-bgvasp}"
LOCK_DIR="${BG_WATCH_LOCK_DIR:-$RUNS/claude_bandgap_watch.lock}"
LOCK_PID_FILE="$LOCK_DIR/pid"
LOCK_HEARTBEAT_FILE="$LOCK_DIR/heartbeat"
WATCH_LOG="${BG_WATCH_LOG:-$RUNS/claude_bandgap_watch.log}"
SUPERVISOR_LOG="${BG_WATCH_SUPERVISOR_LOG:-$RUNS/claude_bandgap_watch.supervisor.log}"

echo "Repository: $REPO"
echo "Supervisor session: $SUPERVISOR_SESSION"
echo "Agent session: $AGENT_SESSION"
echo

if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$SUPERVISOR_SESSION" 2>/dev/null; then
    echo "Supervisor tmux: RUNNING"
  else
    echo "Supervisor tmux: STOPPED"
  fi

  if tmux has-session -t "$AGENT_SESSION" 2>/dev/null; then
    echo "Agent tmux: RUNNING"
  else
    echo "Agent tmux: STOPPED"
  fi
else
  echo "tmux: NOT FOUND"
fi

echo
if [[ -f "$LOCK_PID_FILE" ]]; then
  pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  echo "Watcher lock pid: ${pid:-unknown}"
else
  echo "Watcher lock pid: none"
fi

if [[ -f "$LOCK_HEARTBEAT_FILE" ]]; then
  echo "Watcher heartbeat: $(cat "$LOCK_HEARTBEAT_FILE")"
else
  echo "Watcher heartbeat: none"
fi

echo
if [[ -f "$SUPERVISOR_LOG" ]]; then
  echo "Supervisor log: $SUPERVISOR_LOG"
  tail -n 10 "$SUPERVISOR_LOG"
else
  echo "Supervisor log: missing"
fi

echo
if [[ -f "$WATCH_LOG" ]]; then
  echo "Watcher log: $WATCH_LOG"
  tail -n 10 "$WATCH_LOG"
else
  echo "Watcher log: missing"
fi
