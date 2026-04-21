#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE_DEFAULT="$REPO/scripts/codex_bandgap_watch.env.sh"
ENV_FILE="${BG_WATCH_ENV_FILE:-$ENV_FILE_DEFAULT}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

RUNS="$REPO/runs"
SESSION="${BG_TMUX_SESSION:-bgvasp}"
INTERVAL="${BG_WATCH_INTERVAL:-45}"
COUNT="${BG_WATCH_COUNT:-4000}"
LOG="${BG_WATCH_LOG:-$RUNS/codex_bandgap_watch.log}"
LOCK_DIR="${BG_WATCH_LOCK_DIR:-$RUNS/codex_bandgap_watch.lock}"
LOCK_PID_FILE="$LOCK_DIR/pid"
LOCK_HEARTBEAT_FILE="$LOCK_DIR/heartbeat"
CLI_READY_TIMEOUT="${BG_CLI_READY_TIMEOUT:-120}"
CODEX_EXEC_TIMEOUT="${BG_CODEX_EXEC_TIMEOUT:-300}"
PY="${VASP_AGENT_PYTHON:-/data/xiazeyu/conda/envs/claude/bin/python}"
CONDA_SH="${VASP_AGENT_CONDA_SH:-/data/xiazeyu/conda/etc/profile.d/conda.sh}"
CONDA_ENV="${VASP_AGENT_CONDA_ENV:-claude}"
MAIN="$REPO/main.py"
CODEX="${CODEX_CLI:-$(command -v codex || true)}"
INSTRUCTIONS_MD="$REPO/docs/codexwatch_bandgap_instructions.md"
BG_DATA_ROOT="${BG_DATA_ROOT:-$REPO/data/bandgap}"

read -r -a TASK_DIRS <<<"${BG_TASK_DIRS:-bg_GaN bg_GaP bg_InGaP2 bg_InP}"

mkdir -p "$RUNS"

log() {
  echo "$*" | tee -a "$LOG"
}

update_heartbeat() {
  date -Is >"$LOCK_HEARTBEAT_FILE"
}

release_lock() {
  rm -f "$LOCK_PID_FILE" "$LOCK_HEARTBEAT_FILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" >"$LOCK_PID_FILE"
    update_heartbeat
    return 0
  fi

  if [[ -f "$LOCK_PID_FILE" ]]; then
    local old_pid
    old_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      echo "已有 watcher 在运行: pid=$old_pid lock=$LOCK_DIR" >&2
      return 1
    fi
    echo "检测到陈旧 watcher 锁，清理后继续: pid=${old_pid:-unknown} lock=$LOCK_DIR" >&2
  else
    echo "检测到无 PID 的陈旧 watcher 锁，清理后继续: lock=$LOCK_DIR" >&2
  fi

  rm -f "$LOCK_PID_FILE" "$LOCK_HEARTBEAT_FILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
  echo "$$" >"$LOCK_PID_FILE"
  update_heartbeat
}

on_exit() {
  local ec="$1"
  log "[exit] code=$ec pid=$$"
  release_lock
}

trap 'on_exit $?' EXIT
trap 'ec=$?; log "[err] code=$ec line=$LINENO cmd=${BASH_COMMAND}"; true' ERR

acquire_lock || exit 1

if [[ -z "$CODEX" ]]; then
  echo "未找到 codex CLI" >&2
  exit 1
fi

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" "bash"
fi

initial_prompt_for() {
  local run_dir="$1"
  local material="${run_dir#bg_}"
  local poscar_path="$BG_DATA_ROOT/$material"
  case "$run_dir" in
    bg_*)
      echo "我要计算${material}的能带，POSCAR位于$poscar_path。这个POSCAR已经过结构弛豫，但仍然要做ENCUT和KSPACING收敛测试。使用GPU，PBE阶段使用2张GPU，HSE阶段使用8张GPU。"
      ;;
    *)
      return 1
      ;;
  esac
}

tmux_send_literal() {
  local text="$1"
  tmux send-keys -t "$SESSION" -l "$text"
  tmux send-keys -t "$SESSION" C-m
}

tmux_capture() {
  local lines_back="${1:-200}"
  tmux capture-pane -t "$SESSION" -p -S "-${lines_back}" 2>/dev/null || true
}

agent_running() {
  pgrep -af "[p]ython.*main.py" | grep -q -- "--mode cli"
}

current_main_dir() {
  local line
  line="$(pgrep -af '[p]ython.*main.py' | head -1 || true)"
  [[ -z "$line" ]] && { echo ""; return; }
  if [[ "$line" =~ --dir[[:space:]]+([^[:space:]]+) ]]; then
    echo "${BASH_REMATCH[1]}"
  else
    echo ""
  fi
}

can_resume() {
  local d="$1"
  [[ -f "$RUNS/$d/log.txt" ]] || return 1
  grep -q "session_id" "$RUNS/$d/log.txt"
}

has_bandgap_result() {
  local d="$1"
  local ws="$RUNS/$d"
  local result_dir=""
  [[ -d "$ws" ]] || return 1

  if [[ -d "$ws/hse_scf" ]]; then
    result_dir="$ws/hse_scf"
  elif [[ -d "$ws/hse_calc" ]]; then
    result_dir="$ws/hse_calc"
  else
    result_dir="$ws"
  fi

  [[ -f "$result_dir/vasprun.xml" ]] || return 1
  [[ -f "$result_dir/INCAR_hse" ]] || return 1
  grep -Eq "LHFCALC|HSE06" "$result_dir/OUTCAR" 2>/dev/null || return 1

  local status_json
  status_json="$("$PY" "$REPO/.claude/skills/run_vasp/scripts/check_convergence.py" "$result_dir" 2>/dev/null || true)"
  if [[ -z "$status_json" ]]; then
    return 1
  fi
  python -c 'import json, sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("status") in {"converged", "incomplete_postprocess"} else 1)' <<<"$status_json" >/dev/null 2>&1 || return 1

  "$PY" "$REPO/.claude/skills/bandgap/scripts/gap.py" "$result_dir/vasprun.xml" >/dev/null 2>&1
}

next_incomplete_dir() {
  local d
  for d in "${TASK_DIRS[@]}"; do
    if ! has_bandgap_result "$d"; then
      echo "$d"
      return 0
    fi
  done
  echo ""
}

conversation_has_user_turn() {
  local d="$1"
  local p="$RUNS/$d/conversation_turns.jsonl"
  [[ -f "$p" ]] || return 1
  grep -q '"role": "user"' "$p"
}

wait_for_cli_prompt() {
  local timeout_s="${1:-$CLI_READY_TIMEOUT}"
  local waited=0
  local pane=""

  while ((waited < timeout_s)); do
    pane="$(tmux_capture 80)"
    if grep -q 'You>' <<<"$pane"; then
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

inject_initial_prompt_if_needed() {
  local nd="$1"
  local first_msg=""

  if conversation_has_user_turn "$nd"; then
    return 0
  fi

  if ! wait_for_cli_prompt "$CLI_READY_TIMEOUT"; then
    echo "[warn] CLI 在 ${CLI_READY_TIMEOUT}s 内未出现 You> 提示，暂不注入首句: $nd" | tee -a "$LOG"
    return 0
  fi

  if ! first_msg="$(initial_prompt_for "$nd")"; then
    echo "[warn] 未找到首句任务模板，跳过自动注入: $nd" | tee -a "$LOG"
    return 0
  fi
  if [[ -z "$first_msg" ]]; then
    echo "[warn] 首句任务模板为空，跳过自动注入: $nd" | tee -a "$LOG"
    return 0
  fi

  echo "[auto] 注入首句任务说明: $nd" | tee -a "$LOG"
  tmux_send_literal "$first_msg"
  sleep 2

  if ! conversation_has_user_turn "$nd"; then
    echo "[warn] 首句未落盘，重试一次: $nd" | tee -a "$LOG"
    tmux_send_literal "$first_msg"
  fi
}

auto_start_next_if_idle() {
  if agent_running; then
    local curd=""
    curd="$(current_main_dir)"
    if [[ -n "$curd" ]] && ! conversation_has_user_turn "$curd"; then
      inject_initial_prompt_if_needed "$curd"
    fi
    return 0
  fi

  local nd
  nd="$(next_incomplete_dir)"
  if [[ -z "$nd" ]]; then
    echo "[auto] 四个 bandgap 任务均已完成，无需再启动 main.py" | tee -a "$LOG"
    return 0
  fi

  mkdir -p "$RUNS/$nd"
  local cmd
  if can_resume "$nd"; then
    cmd="source $CONDA_SH && conda activate $CONDA_ENV && cd $REPO && $PY $MAIN --mode cli --dir $nd"
  else
    cmd="source $CONDA_SH && conda activate $CONDA_ENV && cd $REPO && $PY $MAIN --mode cli --dir $nd --no-resume"
  fi

  echo "[auto] 启动下一任务: $nd" | tee -a "$LOG"
  tmux_send_literal "$cmd"
  inject_initial_prompt_if_needed "$nd"
}

build_prompt() {
  cat <<EOF
仓库根目录：$REPO
tmux 会话：$SESSION

请按以下顺序工作：
1. 阅读说明文件：$INSTRUCTIONS_MD
2. 用 Bash 检查 tmux 会话 $SESSION、当前运行的 main.py、以及 runs/bg_* 下相关 log.txt / conversation_turns.jsonl / OUTCAR / OSZICAR / vasprun.xml 状态
3. 判断当前是否需要向 You> 注入一句回复，或者当前体系是否已经可以退出

要求：
- 不能依赖固定规则模板，必须根据当下真实提问内容判断
- 如果当前没有出现明确需要回复的用户提问，输出 WATCH_SKIP
- 如果当前体系已经完成并且可以安全结束该 CLI 会话，输出 WATCH_QUIT
- 如果需要代替人工回复，只输出一行最合适的中文回复到 WATCH_INJECT

最后一行且仅一行必须是：
WATCH_SKIP
或
WATCH_INJECT|<完整一行回复>
或
WATCH_QUIT
EOF
}

parse_watch_line() {
  local msg_file="$1"
  awk 'NF { line = $0 } END { print line }' "$msg_file"
}

handle_watch_action() {
  local last="$1"
  local curd=""

  if [[ "$last" == "WATCH_SKIP" ]]; then
    echo "[parse] WATCH_SKIP" | tee -a "$LOG"
    return 0
  fi

  if [[ "$last" == "WATCH_QUIT" ]]; then
    curd="$(current_main_dir)"
    echo "[parse] WATCH_QUIT" | tee -a "$LOG"
    tmux_send_literal "quit"
    sleep 6
    if [[ -n "$curd" ]]; then
      echo "[parse] 已请求退出当前会话: $curd" | tee -a "$LOG"
    fi
    return 0
  fi

  local pfx="WATCH_INJECT|"
  if [[ "$last" == "$pfx"* ]]; then
    local payload="${last#$pfx}"
    if [[ -n "$payload" ]]; then
      echo "[parse] WATCH_INJECT -> $payload" | tee -a "$LOG"
      tmux_send_literal "$payload"
    else
      echo "[parse] WATCH_INJECT 为空，跳过" | tee -a "$LOG"
    fi
    return 0
  fi

  echo "[parse] 未识别最后一行: ${last:0:200}" | tee -a "$LOG"
}

run_watch_iteration() {
  local i="$1"
  local msg_file prompt ec last

  update_heartbeat
  if ((i > 1)); then
    sleep "$INTERVAL"
  fi

  log ""
  log "######## $(date -Is) 第 $i/$COUNT 次 ########"

  auto_start_next_if_idle || log "[warn] auto_start_next_if_idle 失败，但主循环继续"

  msg_file="$(mktemp /tmp/codex_bandgap_watch_msg.XXXXXX)" || {
    log "[warn] mktemp 失败"
    return 0
  }
  prompt="$(build_prompt)"

  log "[watch] 启动 codex exec"
  set +e
  if command -v timeout >/dev/null 2>&1; then
    timeout --foreground "${CODEX_EXEC_TIMEOUT}s" \
      "$CODEX" exec --disable apps \
      --dangerously-bypass-approvals-and-sandbox \
      -C "$REPO" \
      -o "$msg_file" \
      "$prompt" >>"$LOG" 2>&1
  else
    "$CODEX" exec --disable apps \
      --dangerously-bypass-approvals-and-sandbox \
      -C "$REPO" \
      -o "$msg_file" \
      "$prompt" >>"$LOG" 2>&1
  fi
  ec=$?
  set -e
  log "[watch] codex exec 完成 exit=$ec"

  if [[ "$ec" -ne 0 ]]; then
    if [[ "$ec" -eq 124 ]]; then
      log "[warn] codex exec 超时 ${CODEX_EXEC_TIMEOUT}s，跳过本轮"
    fi
    log "[warn] codex exec 退出码 $ec"
    rm -f "$msg_file"
    return 0
  fi

  if [[ ! -s "$msg_file" ]]; then
    log "[warn] codex exec 未写出最后消息文件"
    rm -f "$msg_file"
    return 0
  fi

  last="$(parse_watch_line "$msg_file")"
  rm -f "$msg_file"
  if [[ -z "$last" ]]; then
    log "[warn] 未解析到 WATCH 行"
    return 0
  fi
  handle_watch_action "$last" || log "[warn] handle_watch_action 失败"
  update_heartbeat
  return 0
}

{
  echo "==== codex bandgap watch 开始 $(date -Is) ===="
  echo "session=$SESSION interval=${INTERVAL}s count=$COUNT"
  echo "log=$LOG"
} | tee -a "$LOG"

for ((i = 1; i <= COUNT; i++)); do
  run_watch_iteration "$i" || log "[warn] 第 $i 轮异常退出，但主循环继续"
done

log "==== codex bandgap watch 结束 $(date -Is) ===="
