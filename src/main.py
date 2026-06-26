import os
import re
import sys
import asyncio
import argparse
import inspect
import json
import shutil
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from claude_agent_sdk import (
    create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient,
    AssistantMessage, ResultMessage, SystemMessage, TextBlock,
    ThinkingBlock, ToolResultBlock, UserMessage,
    ProcessError,
)
from claude_agent_sdk.types import StreamEvent
from src.tool_wrapper import (
    setup_vasp_inputs_tool,
    duckduckgo_search_tool, google_search_tool, visit_webpage_tool, arxiv_search_tool,
)
from src.result_message import result_message_indicates_failure
from webui.web_history import (
    is_skill_injection_context_text,
    parse_log_file_to_ui_events,
    todo_write_in_progress_label,
    todo_write_items_for_ui,
    write_user_turn_log,
)
from src.conversation_store import PERSIST_FILENAME, load_persist_context_for_prompt, persist_on_sdk_message
from src.scheduler import (
    AgentScheduler,
    SchedulerStateStore,
    TaskRegistry,
    WorkspaceSessionIndex,
    load_structured_resume_session_id,
)
from src.litellm_proxy import (
    configure_anthropic_for_litellm,
    direct_model_from_upstream,
    maybe_prefer_direct_upstream,
    maybe_start_litellm,
)

load_dotenv(REPO_ROOT / ".env")

SESSION_LOG_NAME = "log.txt"
CLAUDE_STDERR_LOG = "claude_stderr.log"
WEB_PORT = 18688
RUNS_ROOT = REPO_ROOT / "runs"


def _configure_repo_potcar_dir() -> None:
    """Expose the repository-local POTCAR library to pymatgen and child tools."""
    repo_potcar_dir = REPO_ROOT / "POTCAR_dir"
    current = os.environ.get("PMG_VASP_PSP_DIR")
    if repo_potcar_dir.is_dir() and (not current or not Path(current).exists()):
        os.environ["PMG_VASP_PSP_DIR"] = str(repo_potcar_dir)


_configure_repo_potcar_dir()

# Web：ResultMessage.result 为空且本轮最后一条工具返回 is_error 时，避免界面无文字说明
EMPTY_RESULT_WITH_TOOL_ERROR_FALLBACK = (
    "[系统提示] 本轮在工具执行阶段出现错误，且模型未返回结束摘要。"
    "请查看上文的工具报错；若涉及 `.claude/skills/` 下脚本，请先在仓库根目录执行"
    "（system_prompt 中的 SKILL & `.claude` PATH RULE：`cd` 到 Repository root 再运行）。"
)


def _parse_last_session_id(log_path: Path) -> str | None:
    """从已有 log.txt 的 repr 行中提取最后一次出现的 Claude session_id（用于 --resume）。"""
    if not log_path.is_file():
        return None
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    matches = re.findall(
        r"session_id='([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'",
        text,
    )
    return matches[-1] if matches else None


def resolve_workspace(run_dir: str | None) -> tuple[Path, str | None]:
    """
    解析工作区路径与是否恢复会话。
    - run_dir 为空：新建 runs/<时间戳>，不恢复。
    - run_dir 为单级目录名：兼容旧行为，解析为 runs/<run_dir>。
    - run_dir 为相对/绝对路径：直接按该路径解析。
    若最终目录存在结构化 scheduler state，则优先使用其中的 Claude session_id；
    否则 fallback 到解析 log.txt 供 SDK resume。
    """
    base = RUNS_ROOT.resolve()
    raw = (run_dir or "").strip()
    if not raw:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ws = base / ts
        ws.mkdir(parents=True, exist_ok=True)
        return ws, None

    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        ws = candidate.resolve()
    elif candidate.parent == Path("."):
        # 兼容旧行为：裸目录名默认解释为 runs/<name>。
        ws = (base / candidate.name).resolve()
    else:
        # 支持显式相对路径，例如 runs/foo、./runs/foo、../other/foo。
        ws = candidate.resolve()

    try:
        ws.relative_to(base)
    except ValueError:
        pass
    if not ws.is_dir():
        raise ValueError(f"目录不存在: {ws}")
    resume = load_structured_resume_session_id(ws) or _parse_last_session_id(ws / SESSION_LOG_NAME)
    return ws, resume


def _print_process_error_help(workspace: str, resume: str | None) -> None:
    """CLI 子进程 exit 1 时补充说明（SDK 不把 stderr 放进异常对象）。"""
    p = Path(workspace) / CLAUDE_STDERR_LOG
    api = os.environ.get("ANTHROPIC_BASE_URL", "")
    print("\n[vasp-agent] Claude Code CLI 初始化失败（进程 exit 1）。", file=sys.stderr)
    print(f"  ANTHROPIC_BASE_URL={api or '(未设置)'}", file=sys.stderr)
    if p.is_file():
        print(f"  stderr 已写入: {p}", file=sys.stderr)
        try:
            tail = p.read_text(encoding="utf-8", errors="replace")[-6000:]
            print("  --- claude_stderr.log 尾部 ---", file=sys.stderr)
            print(tail, file=sys.stderr)
        except OSError as ex:
            print(f"  （读取失败: {ex}）", file=sys.stderr)
    print(
        "  常见原因: ① LiteLLM 未在 BASE_URL 监听；② resume 的 session 已失效。\n"
        "  试: curl -sS \"${ANTHROPIC_BASE_URL}/v1/models\" ；或加 --no-resume 跳过恢复会话。",
        file=sys.stderr,
    )
    if resume:
        print(f"  当前 resume session_id: {resume}", file=sys.stderr)


def _make_agent_options(**kwargs) -> ClaudeAgentOptions:
    """Build options while tolerating older claude-agent-sdk versions."""
    supported = inspect.signature(ClaudeAgentOptions).parameters
    return ClaudeAgentOptions(**{k: v for k, v in kwargs.items() if k in supported})


def build_options(
    workspace: str,
    resume: str | None = None,
    persist_context: str | None = None,
) -> ClaudeAgentOptions:
    repo_root = str(RUNS_ROOT.parent.resolve())
    persist_block = ""
    if persist_context and persist_context.strip():
        persist_block = f"""

---
## LOCAL PERSISTED DIALOGUE (injected; new Claude Code session)
The following was saved by VASP Agent to `{PERSIST_FILENAME}` under this workspace. It is **local text recovery**, not a Claude server-side session. **Continue the user's task** (materials / VASP) coherently from this history.
---
{persist_context.strip()}
"""
    mcp_name = "vasp_agent"
    mcp_server = create_sdk_mcp_server(
        name=mcp_name,
        tools=[
            setup_vasp_inputs_tool(workspace),
            duckduckgo_search_tool(),
            google_search_tool(),
            visit_webpage_tool(),
            arxiv_search_tool(),
        ],
    )
    _stderr_first = True

    def _cli_stderr(line: str) -> None:
        """转发 Claude Code CLI 的 stderr，便于排查「exit code 1 / Check stderr」类错误。"""
        nonlocal _stderr_first
        print(f"[claude-code] {line}", file=sys.stderr, flush=True)
        err_path = Path(workspace) / CLAUDE_STDERR_LOG
        try:
            with err_path.open("w" if _stderr_first else "a", encoding="utf-8") as ef:
                ef.write(line + "\n")
            _stderr_first = False
        except OSError:
            pass

    model_name = (
        os.environ.get("CLAUDE_CODE_MODEL")
        or direct_model_from_upstream(os.environ.get("UPSTREAM_MODEL", ""))
        or None
    )

    return _make_agent_options(
        cwd=workspace,
        resume=resume,
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        stderr=_cli_stderr,
        model=model_name,
        enable_file_checkpointing=True,
        system_prompt=f"""Your workspace directory is: {workspace}
All VASP input/output files should be read from and written to this directory.

Repository root (skills, `.claude`, and all paths documented in SKILL files): {repo_root}
The shell cwd for Bash is the **session workspace** above, which is **not** the repository root. Paths like `.claude/skills/...` are relative to **{repo_root}**, not to the workspace.

SKILL & `.claude` PATH RULE (mandatory):
- Any Bash that loads or runs skill assets (Python scripts under `.claude/skills/`, `vasp_runner.py`, `probe_env.py`, `quick_test.py`, sourcing templates, etc.) MUST start by changing directory to the repository root: prefix with `cd "{repo_root}" && ...`, **or** use absolute paths beginning with `{repo_root}/`.
- Do **not** assume `.claude` exists under the session workspace.

VASP FILE PROVENANCE (mandatory): You MUST NOT use Write, Edit, or Bash/heredocs to manually author the full contents of **POSCAR**, **POTCAR**, or **KPOINTS**. Obtain and construct crystal structures through **`Skill: structure`** and its scripts (for example `.claude/skills/structure/scripts/fetch_mp_poscar.py`, `build_surface.py`, or `build_adsorption.py`), or through explicitly documented external retrieval procedures—not by typing lattice vectors and coordinates from memory. Generate **POTCAR** (and the POSCAR copy used with them in the workspace) **only** via **`setup_vasp_inputs`**. If the user explicitly requests a POTCAR variant, pass it through `setup_vasp_inputs` using `potcar_overrides` as a JSON object such as `{{"Cr": "Cr_pv"}}`; do not generate, edit, concatenate, or copy POTCAR manually with Bash/Python as a fallback. Prefer **KSPACING** (and optionally **KGAMMA**) in **INCAR** so **`setup_vasp_inputs`** does not create a **KPOINTS** file; only when **KSPACING** is absent does the tool write **KPOINTS** from density. You MAY create or adjust **INCAR** by copying skill templates and changing parameters (ENCUT, ISMEAR, KSPACING, etc.).

CRITICAL INTERACTION RULE: You MUST NOT call or attempt to use the `AskUserQuestion` tool. Instead, whenever you finish a major workflow step, encounter an error, or need permission to proceed to a computationally expensive task (like running VASP), you MUST output a plain text block. In this text block, clearly summarize what you have achieved so far, and explicitly ask the user for confirmation to proceed to the next step. NEVER terminate your turn silently without reporting your status.

END OF TURN & ANTI-SILENCE REQUIREMENT (CRITICAL):
You are STRICTLY FORBIDDEN from ending a conversation turn silently.
1. The LAST THING the user sees in your turn MUST ALWAYS be ordinary human-readable text (Chinese or English prose; Markdown allowed).
2. If your last action was a tool call (especially if the tool returned an ERROR, 'Exit code 1', or empty output), you MUST explicitly generate a text block analyzing the result or explaining the failure before waiting for the user.
3. Never end a turn with only tool calls, empty text, placeholder or control tokens (e.g. strings like "<ctrl46>" or similar), or meaningless repeated characters. If you are stuck, explicitly say (in the user's language when appropriate): "我遇到了问题，需要您的帮助..." and describe the roadblock.

MARKDOWN & WEB UI (strikethrough / `~~`):
User-visible replies are rendered as Markdown (GFM). A pair of `~~` starts GitHub-Flavored-Markdown **strikethrough**, which is often triggered by accident in paths or ranges (e.g. `e_300~~e_500`). In normal prose, **do not** type two tildes in a row. For ranges or "A to B", use an en dash (–), a hyphen (-), the word "to", Chinese 「至／到」, or a **single** `~` if needed—**not** `~~`.

SKILL IMPROVEMENT: When you have fully completed a task that involved using a SKILL, proactively reflect on the execution trajectory. If the SKILL could be improved (unclear steps, missing edge cases, potential errors), use simple-skill-creator to update it and present the diff to the user for confirmation. Only do this once the task is truly complete, not mid-task.

BASH ENVIRONMENT PROBES — NO "FAIL-FAST" CHAINS (CRITICAL):
Fragile probes that exit non-zero on the first missing binary cause Bash tools to return ERROR. In parallel tool rounds, that can trigger **Sibling tool call errored** for other tools (e.g. Skill) in the same assistant message—even though Skill content is fine.
Rules:
1. Do **not** use `&&` to chain probes where later commands should still run if an earlier command is missing (unless you intentionally want short-circuit).
2. Do **not** use `which a b c` / `command -v a b c` with multiple names if **any** may be absent: many shells report failure if **any** name is not found.
3. Prefer **separate** Bash invocations, or **one** Bash that uses `;`, `|| true`, or a `for` loop so each check is independent.
4. Avoid launching **Skill** (or other heavy tools) **in parallel** with environment-probing Bash in the **same** turn; probe first, then call Skill when the probe is clean.

Examples (copy the pattern, adapt paths):
- **BAD:** `command -v sbatch && command -v mpirun && command -v vasp_std` → exits at first missing command; rest never runs.
- **BAD:** `which mpirun vasp_std vasp_gpu` → exit 1 if any single binary is missing.
- **BAD:** `nvidia-smi -L && which mpirun vasp_std` → GPUs list OK, but if `which` fails the whole tool returns error.
- **GOOD:** `hostname; nvidia-smi -L 2>/dev/null || true` then separately: `command -v mpirun || echo "mpirun: missing"; command -v vasp_std || echo "vasp_std: missing"`
- **GOOD:** `for c in sbatch qsub mpirun vasp_std; do printf "%s: " "$c"; command -v "$c" || echo missing; done`
- **GOOD (after user gives env script):** `source /path/to/env.sh && command -v vasp_std && command -v mpirun` — here `&&` is OK because the user explicitly provided the environment.

MISSING DEPENDENCY RULE:
If you encounter 'command not found', 'Exit code 1' when probing for software, or 'ModuleNotFoundError':
1. DO NOT attempt to endlessly run alternative Bash commands or 'Read' generic system files to guess the path.
2. IMMEDIATELY STOP using tools.
3. Output a plain text message to the user, reporting exactly which executable or module is missing, and ask them to provide the explicit path or the environment setup commands (e.g. module load, export PATH).
4. DO NOT use generic 'Read' tools on binary files (like PDF) as a substitute for fixing the environment.

VASP ORCHESTRATION — PRE-CHECK TODO LIST (before the first real VASP computation):
Use **TodoWrite** to mirror this checklist and advance items to `completed` / `in_progress` as you go. This is **staged orchestration**, not a one-shot essay; you still complete each stage before starting heavy compute.

1. **Identify intent** — Quick test (e.g. INCAR/convergence sanity) vs production run; align with the user's goal.
2. **Probe environment** — **Prefer** `run_vasp` skill `scripts/probe_env.py` with Bash, obeying SKILL & `.claude` PATH RULE, e.g. `cd "{repo_root}" && python .claude/skills/run_vasp/scripts/probe_env.py` (CPU/ GPU / `sbatch`/`qsub` in PATH—no `sinfo` required). Optional extra Bash: CPU `lscpu`; GPU `nvidia-smi -L` (ignore if missing); node `hostname`. Treat Slurm as present if `sbatch` exists, PBS if `qsub` exists. Run `sinfo` / `qstat` **only** if `command -v` succeeds for them. **Never** chain `lscpu`, `nvidia-smi`, and optional `sinfo`/`qstat` with `&&` in one command (see BASH ENVIRONMENT PROBES).
3. **If BOTH GPU and CPU are detected** — Do not default to CPU. Ask the user: GPU vs CPU, and GPU count if GPU.
4. **If a workload manager (Slurm/PBS) is detected** — Do not run heavy jobs locally without user input. Ask for partition/queue, nodes, walltime, and other cluster-specific parameters needed for the job script.
5. **Confirm execution strategy** — After user answers, present the final plan as a **runner-facing command**: prefer the exact `python .claude/skills/run_vasp/scripts/vasp_runner.py ...` command with its parameters and log-file/log-prefix choices, or a full sbatch/qsub script. Explain, when useful, that `vasp_runner.py` will generate the corresponding `mpirun` / scheduler run lines in the background. Get **explicit confirmation** before launching expensive work. **Never** fire heavy local VASP work on a login node without this confirmation.

LOCAL COMPUTE — BASH `run_in_background` (mandatory):
- Any **real** workload (VASP, `vasp_runner`, `mpirun`, or anything expected to run **minutes+**) MUST be launched with **`run_in_background: true`** on Bash so the tool returns immediately and does not freeze the session (especially **web** chat). Use `nohup`, `&`, env scripts, and `run_vasp` skill patterns as documented. For formal VASP submission, prefer **`vasp_runner.py` / `quick_test.py`** as the user-facing entrypoints; the assistant should organize and confirm the runner command, and let the runner generate raw `mpirun` / job-script run lines in the background instead of hand-writing them in assistant Bash.
- **Monitoring:** Periodic checking is encouraged. Prefer a coarse cadence for long jobs (for example, every 5 minutes) and only tighten the cadence near completion or when diagnosing anomalies. You may use `grep`/`tail` on `OUTCAR`, `OSZICAR`, logs, and `pgrep`/`ps` to inspect status.
- **Sleep usage:** `sleep 300`-style waiting is allowed and often desirable for long VASP jobs, **provided** it does not freeze the user-facing session. Prefer **background** helper loops/scripts or non-blocking polling; if you use foreground waiting, keep the UI responsiveness tradeoff in mind and explain it briefly when relevant.
- **`TaskOutput` vs frozen UI (critical):** After a long Bash job is started (including when the host auto-backgrounds `vasp_runner`), avoid overly chatty polling. You **must still** fully orchestrate the run yourself (poll until done, then read OUTCAR, run `check_convergence.py`, etc.), but prefer **periodic** checks over rapid-fire checks: use **`TaskOutput` with `block: false`** at a sensible cadence, typically coarse for long jobs, or a background Bash helper that sleeps between checks. Do not use **`TaskOutput` and `block: true`** with a single huge timeout that pins the whole agent turn and **freezes web/IDE chat** until VASP finishes.
- **Slurm / PBS:** Submit → record **Job ID** → poll `squeue`/`qstat` in brief commands; do not keep one foreground Bash open until the job finishes.

PROCESS OWNERSHIP & TERMINATION SAFETY (CRITICAL):
- You MUST treat process termination as a high-risk action. **Never** use broad kill commands such as `pkill`, `killall`, `pkill -f vasp_std`, `killall vasp_std`, or pattern-based `kill $(pgrep ...)` for VASP or MPI workloads.
- When the user asks to stop/pause/cancel a VASP run, DO NOT hand-write any shell kill pipeline. Use the run_vasp termination entrypoint instead:
  - State-backed run: `cd "{repo_root}" && python .claude/skills/run_vasp/scripts/terminate.py --work-dir "<exact_task_dir>" --reason "<reason>"`
  - Legacy hand-launched run without `.vasp_run_state.json`: first inspect with `cd "{repo_root}" && python .claude/skills/run_vasp/scripts/terminate.py --work-dir "<exact_task_dir>" --allow-cwd-scan --dry-run`, then, only if every listed PID has `/proc/<pid>/cwd` exactly equal to the target task directory, run the same command without `--dry-run`.
- `pkill -f` is especially forbidden: it can match the Bash/tool wrapper command line containing the pattern itself and terminate the message reader or agent process.
- You MAY terminate a process **only if all of the following are true**:
  1. You launched that exact workload earlier in the same session/workflow; and
  2. You have concrete ownership evidence tying the running PID/job to the exact workspace/run directory or recorded task/job id you started; and
  3. You have first checked that it is actually stale, wedged, or no longer desired (for example: log file no longer changes, task state is terminal-but-process-remains, or the user explicitly asked to stop it).
- `pgrep`/`ps` name matches alone are **not** ownership evidence. A count like `pgrep -f vasp_std | wc -l` is never sufficient justification to kill anything.
- If ownership cannot be proven, you must **not** terminate the process. Instead, report what you observed, explain the ambiguity, and ask the user before any destructive action.
- If termination is justified, target only the specific PID(s) or scheduler job ID(s) you verified belong to the workload you started. Prefer the narrowest possible command and explain the evidence in user-facing text before or immediately after the action.

RESTART-IN-PLACE SAFETY FOR GPU / MPI FAILURES (CRITICAL):
- If a VASP step fails, wedges, or reports GPU/MPI errors and you plan to retry the **same physical calculation** in the **same work directory** (for example the same `pbe_scf`, `hse_scf`, or convergence-point directory), you MUST first check whether the previous owned `mpirun` / `vasp_*` process tree is still alive.
- You MUST NOT launch a second `mpirun` / VASP process into the same directory while an earlier owned run for that directory may still be alive. In particular, do **not** append `&` to start a replacement run in the background until you have proven the old owned PID tree has exited (or you have explicitly terminated that exact old owned PID tree).
- When changing GPU layout after a failure (for example retrying from 8 GPUs to 7 GPUs), prefer restarting through `vasp_runner.py` / `quick_test.py` with updated arguments, not by hand-writing a fresh ad-hoc `mpirun` command.
- Before any in-place retry, verify all of the following and report them in ordinary text: the old task/job id or PID evidence, whether the old run is still alive, whether it was terminated, and the exact replacement command you will use.
- If you cannot prove the old run is gone, stop and ask the user instead of starting a second run that could race on the same files or log.

ITERATIVE EXECUTION RULE: When performing parameter sweeps or convergence tests, DO NOT write and execute monolithic Python/Bash scripts containing loops to run VASP multiple times. Instead, manage the loop in your reasoning and run **each** heavy step **one at a time** with **`run_in_background: true`** (or the workload manager per `run_vasp`). This preserves intermediate checks and avoids many uncontrolled concurrent processes.

POTCAR SELECTION RULE: Use the pymatgen / Materials Project **recommended** pseudopotential for each element. For transition metals, alkali, alkaline-earth and many heavy elements this is the semi-core variant (e.g., Ti_pv, Fe_pv, Mn_pv, Cr_pv, Ni_pv, Li_sv, Ba_sv, Ca_sv, Na_pv, Sn_d, Pb_d), NOT the bare standard potential. `setup_vasp_inputs` applies this recommended mapping automatically. Do NOT downgrade to the fewest-valence-electron standard version to save computational cost: doing so shifts the total-energy reference (making energies incomparable with reference/benchmark data) and loses accuracy where semi-core states matter. Only deviate from the recommended choice if the user explicitly requests it, and then pass the exact element-to-POTCAR map via `potcar_overrides` (for example `{{"Cr": "Cr_pv"}}`). If `setup_vasp_inputs` rejects the override, stop and report the error instead of bypassing the tool.
{persist_block}""",
        mcp_servers={mcp_name: mcp_server},
        allowed_tools=[
            "Skill",
            f"mcp__{mcp_name}__setup_vasp_inputs",
            f"mcp__{mcp_name}__duckduckgo_search",
            f"mcp__{mcp_name}__google_search",
            f"mcp__{mcp_name}__visit_webpage",
            f"mcp__{mcp_name}__arxiv_search",
        ],
    )


# ---------------------------------------------------------------------------
# CLI mode
# ---------------------------------------------------------------------------

async def _async_input(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: input(prompt))


def _append_sdk_log_line(log_file, msg: Any) -> None:
    """每条 SDK 消息立即写入 log（与流式顺序一致）。"""
    log_file.write(repr(msg) + "\n")
    log_file.flush()
    print(repr(msg))


def _dispatch_message_to_cli(msg: Any) -> None:
    """CLI 下将单条消息打印到终端（不含已写入 log 的 repr）。"""
    if isinstance(msg, StreamEvent):
        return

    subtype = getattr(msg, "subtype", "") or ""
    data = getattr(msg, "data", None)
    data = data if isinstance(data, dict) else {}
    if isinstance(msg, SystemMessage) or subtype in {"task_notification", "task_started", "task_updated"}:
        if subtype == "task_notification":
            summary = data.get("summary") or ""
            if summary:
                print(f"[后台任务] {summary}\n", flush=True)
        elif subtype == "task_started":
            desc = data.get("description") or ""
            if desc:
                print(f"[后台任务] 已启动: {desc}\n", flush=True)
        elif subtype == "task_updated":
            task_id = data.get("task_id") or ""
            patch = data.get("patch") if isinstance(data.get("patch"), dict) else {}
            status = patch.get("status") or data.get("status") or "updated"
            print(f"[后台任务] {task_id} {status}\n", flush=True)
        return

    if isinstance(msg, AssistantMessage):
        for block in getattr(msg, "content", []):
            block_type = type(block).__name__
            if block_type == "TextBlock" or isinstance(block, TextBlock):
                print(f"Agent> {block.text}\n", flush=True)
            elif block_type == "ToolUseBlock" or getattr(block, "type", None) == "tool_use":
                tool_name = getattr(block, "name", "UnknownTool")
                try:
                    input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                except Exception:
                    input_str = str(getattr(block, "input", ""))
                print(f" [🛠 工具调用] {tool_name}\n {input_str}\n", flush=True)
        return

    if isinstance(msg, UserMessage):
        for block in getattr(msg, "content", []):
            if type(block).__name__ == "ToolResultBlock":
                content = getattr(block, "content", "")
                is_error = getattr(block, "is_error", False)
                status_icon = "❌" if is_error else "✅"
                content_str = str(content)
                if len(content_str) > 300:
                    content_str = content_str[:300] + "\n ... [内容已截断]"
                print(f" [{status_icon} 工具返回结果]\n {content_str}\n", flush=True)
        return

    if isinstance(msg, ResultMessage):
        failed = result_message_indicates_failure(msg)
        status = "✗ 出错" if failed else "✓ 完成"
        extra = f"  subtype={msg.subtype!r}" if failed else ""
        print(f"\n{status}  轮次: {msg.num_turns}{extra}\n", flush=True)


async def _cli_sdk_receive_loop(
    client: ClaudeSDKClient,
    log_file,
    workspace: str,
    persist_state: dict[str, Any],
    scheduler: AgentScheduler,
) -> None:
    """持续消费 SDK 消息流（ClaudeSDKClient.receive_messages）。

    与 receive_response()（在 ResultMessage 处结束）不同：空闲等待用户输入时仍可收到
    SystemMessage（如 task_notification），从而及时写入 log 与终端。
    """
    async for msg in client.receive_messages():
        _append_sdk_log_line(log_file, msg)
        scheduler.observe_message(msg)
        persist_on_sdk_message(workspace, msg, persist_state)
        _dispatch_message_to_cli(msg)
        if isinstance(msg, ResultMessage):
            failed = result_message_indicates_failure(msg)
            pending = scheduler.complete_result(msg, failed=failed)
            if pending:
                print("[scheduler] 已打断，正在处理新指令...\n", flush=True)
                write_user_turn_log(log_file, pending)
                await scheduler.submit(pending)


async def cli_agent_loop(
    client: ClaudeSDKClient,
    log_file,
    workspace: str,
    scheduler: AgentScheduler,
) -> None:
    persist_state: dict[str, Any] = {"persist_assistant_buf": ""}
    drain = asyncio.create_task(
        _cli_sdk_receive_loop(client, log_file, workspace, persist_state, scheduler)
    )
    try:
        while True:
            try:
                user_input = await _async_input("You> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if user_input.strip().lower() in ("quit", "exit", "q"):
                break
            if not user_input.strip():
                continue

            control = await scheduler.handle_control_command(user_input, allow_interrupt=True)
            if control.handled:
                if control.text:
                    print(f"[scheduler] {control.text}\n", flush=True)
                continue

            if scheduler.busy:
                print("正在打断当前回复并切换到新指令...\n", flush=True)
                await scheduler.interrupt(user_input)
            else:
                print("思考中...\n", flush=True)
                write_user_turn_log(log_file, user_input)
                await scheduler.submit(user_input)
    finally:
        drain.cancel()
        with suppress(asyncio.CancelledError):
            await drain


async def cli_main(
    workspace: str,
    resume: str | None,
    log_append: bool,
    persist_context: str | None = None,
) -> None:
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    log_path = ws / SESSION_LOG_NAME

    print(f"VASP Agent (CLI 模式)  |  输入 quit 或 exit 退出")
    print(f"工作目录: {workspace}")
    if resume:
        print(f"恢复会话: {resume}（结构化状态或 log.txt）")
    else:
        print("新会话（无 resume 或 log 中无 session_id）")
    if persist_context:
        print(f"已注入本地持久化历史: {Path(workspace) / PERSIST_FILENAME}（约 {len(persist_context)} 字符）")
    print(f"日志写入: {log_path}（{'追加' if log_append else '新建'}）\n")

    log_mode = "a" if log_append else "w"
    log_file = open(log_path, log_mode, encoding="utf-8")
    store = SchedulerStateStore(workspace)
    try:
        try:
            async with ClaudeSDKClient(
                options=build_options(workspace, resume=resume, persist_context=persist_context),
            ) as client:
                scheduler = AgentScheduler(client, store, TaskRegistry(store))
                await cli_agent_loop(client, log_file, workspace, scheduler)
        except ProcessError:
            _print_process_error_help(workspace, resume)
            raise
    finally:
        store.close()
        log_file.close()


# ---------------------------------------------------------------------------
# Web mode
# ---------------------------------------------------------------------------

def _format_tool_result_content(content: Any) -> str:
    """将 ToolResultBlock.content 转为网页展示的纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                else:
                    try:
                        parts.append(json.dumps(item, ensure_ascii=False, indent=2))
                    except Exception:
                        parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


async def _dispatch_message_to_web(
    msg: Any, ui: Any, session_state: dict[str, Any] | None = None,
) -> None:
    """将单条 SDK 消息推到网页（StreamEvent 仅忽略 UI；SystemMessage 仅展示任务相关）。"""
    if isinstance(msg, StreamEvent):
        return

    subtype = getattr(msg, "subtype", "") or ""
    data = getattr(msg, "data", None)
    data = data if isinstance(data, dict) else {}
    if isinstance(msg, SystemMessage) or subtype in {"task_notification", "task_started", "task_updated"}:
        if subtype == "task_notification":
            summary = data.get("summary") or ""
            if summary:
                await ui.send({"type": "agent_text", "text": f"[后台任务] {summary}"})
        elif subtype == "task_started":
            desc = data.get("description") or ""
            if desc:
                await ui.send({"type": "agent_text", "text": f"[后台任务] 已启动: {desc}"})
        elif subtype == "task_updated":
            task_id = data.get("task_id") or ""
            patch = data.get("patch") if isinstance(data.get("patch"), dict) else {}
            status = patch.get("status") or data.get("status") or "updated"
            await ui.send({"type": "agent_text", "text": f"[后台任务] {task_id} {status}"})
        return

    if isinstance(msg, AssistantMessage):
        for block in getattr(msg, "content", []):
            block_type = type(block).__name__
            if block_type == "TextBlock" or isinstance(block, TextBlock):
                await ui.send({"type": "agent_text", "text": block.text})
            elif block_type == "ThinkingBlock" or isinstance(block, ThinkingBlock):
                await ui.send(
                    {"type": "agent_text", "text": "[思考]\n" + getattr(block, "thinking", "")}
                )
            elif block_type == "ToolUseBlock" or getattr(block, "type", None) == "tool_use":
                tname = getattr(block, "name", "?")
                tid = getattr(block, "id", "") or ""
                try:
                    input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                except Exception:
                    input_str = str(getattr(block, "input", ""))
                await ui.send(
                    {
                        "type": "tool_use",
                        "name": tname,
                        "input_str": input_str,
                        "tool_use_id": tid,
                    }
                )
                if tname == "TodoWrite":
                    tw_in = getattr(block, "input", None) or {}
                    await ui.send(
                        {
                            "type": "todo_update",
                            "todos": todo_write_items_for_ui(tw_in),
                        }
                    )
                    tw_label = todo_write_in_progress_label(tw_in)
                    if tw_label:
                        await ui.send(
                            {
                                "type": "status",
                                "text": f"进行中: {tw_label}",
                                "thinking": True,
                            }
                        )
        return

    if isinstance(msg, UserMessage):
        raw = getattr(msg, "content", None)
        blocks = raw if isinstance(raw, list) else []
        for block in blocks:
            if isinstance(block, ToolResultBlock):
                tid = getattr(block, "tool_use_id", "") or ""
                err = getattr(block, "is_error", None)
                is_err = bool(err) if err is not None else False
                if session_state is not None:
                    session_state["last_tool_error"] = is_err
                body = _format_tool_result_content(getattr(block, "content", None))
                await ui.send(
                    {
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "is_error": is_err,
                        "content_str": body,
                    }
                )
            elif isinstance(block, TextBlock):
                text = getattr(block, "text", "")
                if text.strip() == "[Request interrupted by user]":
                    if session_state is not None:
                        session_state["saw_interrupt_context"] = True
                    continue
                if is_skill_injection_context_text(block.text):
                    await ui.send(
                        {
                            "type": "agent_text",
                            "text": block.text,
                            "collapsed": True,
                            "collapsed_label": "Skill 正文（点击展开）",
                        }
                    )
                else:
                    await ui.send(
                        {"type": "agent_text", "text": "[上下文]\n" + block.text}
                    )
        return

    if isinstance(msg, ResultMessage):
        has_pending_interrupt = bool(
            session_state is not None
            and (session_state.get("pending_interrupt_text") or "").strip()
        )
        user_interrupted = bool(
            session_state is not None
            and session_state.get("user_interrupt_requested")
        )
        result_text = (getattr(msg, "result", None) or "").strip()
        if (
            session_state is not None
            and not user_interrupted
            and not result_text
            and session_state.get("last_tool_error")
        ):
            await ui.send({"type": "agent_text", "text": EMPTY_RESULT_WITH_TOOL_ERROR_FALLBACK})
        if session_state is not None:
            session_state["last_tool_error"] = False
        failed = result_message_indicates_failure(msg) and not user_interrupted
        await ui.send({
            "type": "result",
            "turns": getattr(msg, "num_turns", 0),
            "error": failed,
            "interrupted": user_interrupted,
            "pending_interrupt": has_pending_interrupt,
            "subtype": getattr(msg, "subtype", None) or "",
            "summary": getattr(msg, "result", None) or "",
        })
        if session_state is not None:
            session_state["user_interrupt_requested"] = False
            session_state["saw_interrupt_context"] = False
        if has_pending_interrupt:
            await ui.send({"type": "status", "text": "已打断，正在切换到新指令...", "thinking": True})
        else:
            await ui.send({"type": "status", "text": "就绪 — 请在下方输入", "thinking": False})
            await ui.send({"type": "done"})


async def _web_sdk_receive_loop(
    client: ClaudeSDKClient,
    log_file,
    ui: Any,
    session_state: dict[str, Any],
    workspace: str,
    scheduler: AgentScheduler,
) -> None:
    """后台持续 consume receive_messages()，与主协程中仅负责 query(用户输入) 分离。"""
    try:
        async for msg in client.receive_messages():
            _append_sdk_log_line(log_file, msg)
            scheduler.observe_message(msg)
            persist_on_sdk_message(workspace, msg, session_state)
            if scheduler.pending_after_interrupt:
                session_state["pending_interrupt_text"] = scheduler.pending_after_interrupt
            else:
                session_state.pop("pending_interrupt_text", None)
            await _dispatch_message_to_web(msg, ui, session_state)
            if isinstance(msg, ResultMessage):
                failed = result_message_indicates_failure(msg)
                pending = scheduler.complete_result(msg, failed=failed)
                session_state["busy"] = scheduler.busy
                session_state["interrupt_in_flight"] = scheduler.interrupt_in_flight
                session_state.pop("pending_interrupt_text", None)
                if pending:
                    await ui.send({"type": "status", "text": "处理中断后的新指令...", "thinking": True})
                    write_user_turn_log(log_file, pending)
                    session_state["last_tool_error"] = False
                    await scheduler.submit(pending)
                    session_state["busy"] = scheduler.busy
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await ui.send({"type": "agent_text", "text": f"[错误] SDK 消息流异常: {e}"})
        raise


async def web_agent_loop(
    client: ClaudeSDKClient,
    log_file,
    ui,
    session_state: dict[str, Any],
    workspace: str,
    scheduler: AgentScheduler,
) -> None:
    drain = asyncio.create_task(
        _web_sdk_receive_loop(client, log_file, ui, session_state, workspace, scheduler),
    )

    async def submit_user_message(text: str) -> None:
        await ui.send({"type": "status", "text": "思考中...", "thinking": True})
        write_user_turn_log(log_file, text)
        session_state["last_tool_error"] = False
        await scheduler.submit(text)
        session_state["busy"] = scheduler.busy

    async def interrupt_current_turn(text: str) -> None:
        pending = text.strip()
        session_state["user_interrupt_requested"] = True
        if pending:
            await ui.send({"type": "status", "text": "正在打断并准备新指令...", "thinking": True})
        else:
            await ui.send({"type": "status", "text": "正在停止当前回复...", "thinking": True})

        try:
            await scheduler.interrupt(pending)
            session_state["busy"] = scheduler.busy
            session_state["interrupt_in_flight"] = scheduler.interrupt_in_flight
            if scheduler.pending_after_interrupt:
                session_state["pending_interrupt_text"] = scheduler.pending_after_interrupt
            else:
                session_state.pop("pending_interrupt_text", None)
        except Exception as e:
            session_state["user_interrupt_requested"] = False
            scheduler.interrupt_in_flight = False
            session_state["interrupt_in_flight"] = False
            await ui.send({"type": "agent_text", "text": f"[错误] 打断失败: {e}"})
            await ui.send({"type": "status", "text": "打断失败，仍在等待当前回复...", "thinking": True})

    try:
        while True:
            event = await ui.input_queue.get()
            if isinstance(event, dict):
                event_type = event.get("type") or "user_message"
                user_input = str(event.get("text") or "")
            else:
                event_type = "user_message"
                user_input = str(event)
            if user_input.lower() in ("quit", "exit"):
                break

            control = await scheduler.handle_control_command(user_input, allow_interrupt=True)
            if control.handled:
                if control.text:
                    await ui.send({"type": "agent_text", "text": f"[scheduler]\n{control.text}"})
                if scheduler.busy or control.thinking:
                    await ui.send({"type": "status", "text": "仍在处理当前回复...", "thinking": True})
                else:
                    await ui.send({"type": "status", "text": "就绪 — 请在下方输入", "thinking": False})
                    if control.done:
                        await ui.send({"type": "done"})
                continue

            if event_type == "interrupt":
                if scheduler.busy:
                    await interrupt_current_turn(user_input)
                elif user_input.strip():
                    await submit_user_message(user_input)
                else:
                    await ui.send({"type": "status", "text": "就绪 — 请在下方输入", "thinking": False})
                    await ui.send({"type": "done"})
                continue

            if scheduler.busy:
                await interrupt_current_turn(user_input)
            else:
                await submit_user_message(user_input)
    finally:
        drain.cancel()
        with suppress(asyncio.CancelledError):
            await drain


class _SessionSender:
    def __init__(self, ui: Any, agent_session_id: str) -> None:
        self.ui = ui
        self.agent_session_id = agent_session_id

    async def send(self, data: dict[str, Any]) -> None:
        payload = dict(data)
        payload.setdefault("agent_session_id", self.agent_session_id)
        await self.ui.send(payload)


def _with_session_id(events: list[dict[str, Any]], agent_session_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for event in events:
        item = dict(event)
        item.setdefault("agent_session_id", agent_session_id)
        out.append(item)
    return out


def _tasks_for_ui(store: SchedulerStateStore) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for task in store.list_tasks(include_terminal=True):
        tasks.append(
            {
                "task_id": task.get("task_id"),
                "kind": task.get("kind"),
                "status": task.get("status"),
                "label": task.get("label"),
                "owner": task.get("owner"),
                "updated_at": task.get("updated_at"),
            }
        )
    return tasks


class WorkspaceRuntime:
    def __init__(
        self,
        *,
        record: dict[str, Any],
        ui: Any,
        index: WorkspaceSessionIndex,
    ) -> None:
        self.record = record
        self.agent_session_id = str(record["agent_session_id"])
        self.workspace = Path(record["workspace"])
        self.ui = ui
        self.index = index
        self.sender = _SessionSender(ui, self.agent_session_id)
        self.log_file = None
        self.store: SchedulerStateStore | None = None
        self.client: ClaudeSDKClient | None = None
        self.scheduler: AgentScheduler | None = None
        self.session_state: dict[str, Any] = {
            "busy": False,
            "interrupt_in_flight": False,
            "user_interrupt_requested": False,
            "last_tool_error": False,
            "persist_assistant_buf": "",
        }
        self.receive_task: asyncio.Task | None = None
        self.started = False

    async def start(self) -> None:
        if self.started:
            self.index.touch(self.agent_session_id)
            return

        self.workspace.mkdir(parents=True, exist_ok=True)
        log_path = self.workspace / SESSION_LOG_NAME
        resume = load_structured_resume_session_id(self.workspace) or _parse_last_session_id(log_path)
        persist_context = None if resume else load_persist_context_for_prompt(self.workspace)
        log_mode = "a" if log_path.exists() else "w"
        self.log_file = open(log_path, log_mode, encoding="utf-8")
        self.store = SchedulerStateStore(self.workspace)
        self.index.update_runtime_state(self.agent_session_id, status="opening", claude_session_id=resume)
        self.client = ClaudeSDKClient(
            options=build_options(str(self.workspace), resume=resume, persist_context=persist_context),
        )
        try:
            await self.client.connect()
        except ProcessError:
            _print_process_error_help(str(self.workspace), resume)
            self.index.update_runtime_state(self.agent_session_id, status="error")
            raise
        self.scheduler = AgentScheduler(self.client, self.store, TaskRegistry(self.store))
        self.receive_task = asyncio.create_task(self._receive_loop())
        self.started = True
        self.index.update_runtime_state(self.agent_session_id, status="idle", claude_session_id=resume)
        await self.sender.send({"type": "log_path", "path": str(log_path)})
        await self.sender.send({"type": "task_snapshot", "tasks": _tasks_for_ui(self.store)})
        await self.send_session_list()

    async def close(self) -> None:
        if self.receive_task:
            self.receive_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.receive_task
        if self.client:
            await self.client.disconnect()
        if self.store:
            self.store.close()
        if self.log_file:
            self.log_file.close()
        self.index.update_runtime_state(self.agent_session_id, status="detached")
        self.started = False

    def history_events(self) -> list[dict[str, Any]]:
        log_path = self.workspace / SESSION_LOG_NAME
        events = parse_log_file_to_ui_events(
            log_path,
            format_tool_result=_format_tool_result_content,
            result_failed=result_message_indicates_failure,
        )
        return _with_session_id(events, self.agent_session_id)

    async def send_snapshot(self, ws: Any | None = None) -> None:
        if not self.store:
            return
        payload = {
            "type": "task_snapshot",
            "agent_session_id": self.agent_session_id,
            "tasks": _tasks_for_ui(self.store),
        }
        if ws is not None:
            await self.ui.send_to(ws, payload)
        else:
            await self.ui.send(payload)

    async def send_session_list(self) -> None:
        await self.ui.send(
            {
                "type": "session_list",
                "sessions": self.index.list_sessions(),
            }
        )

    async def handle_user_message(self, text: str) -> None:
        await self.start()
        assert self.scheduler is not None
        assert self.log_file is not None

        control = await self.scheduler.handle_control_command(text, allow_interrupt=True)
        if control.handled:
            if control.text:
                await self.sender.send({"type": "agent_text", "text": f"[scheduler]\n{control.text}"})
            await self.send_snapshot()
            if self.scheduler.busy or control.thinking:
                await self.sender.send({"type": "status", "text": "仍在处理当前回复...", "thinking": True})
            else:
                await self.sender.send({"type": "status", "text": "就绪 — 请在下方输入", "thinking": False})
                if control.done:
                    await self.sender.send({"type": "done"})
            return

        if self.scheduler.busy:
            await self._interrupt_current_turn(text)
            return

        await self.sender.send({"type": "user_message", "text": text})
        await self.sender.send({"type": "status", "text": "思考中...", "thinking": True})
        write_user_turn_log(self.log_file, text)
        self.session_state["last_tool_error"] = False
        await self.scheduler.submit(text)
        self.session_state["busy"] = self.scheduler.busy
        self.index.update_runtime_state(self.agent_session_id, status="running")
        await self.send_session_list()

    async def handle_interrupt(self, text: str) -> None:
        await self.start()
        assert self.scheduler is not None
        if self.scheduler.busy:
            await self._interrupt_current_turn(text)
        elif text.strip():
            await self.handle_user_message(text)
        else:
            await self.sender.send({"type": "status", "text": "就绪 — 请在下方输入", "thinking": False})
            await self.sender.send({"type": "done"})

    async def stop_task(self, task_id: str) -> None:
        await self.start()
        assert self.scheduler is not None
        response = await self.scheduler.handle_control_command(
            f"/stop-claude-task {task_id}",
            allow_interrupt=True,
        )
        if response.text:
            await self.sender.send({"type": "agent_text", "text": f"[scheduler]\n{response.text}"})
        await self.send_snapshot()

    async def _interrupt_current_turn(self, text: str) -> None:
        assert self.scheduler is not None
        pending = text.strip()
        self.session_state["user_interrupt_requested"] = True
        if pending:
            await self.sender.send({"type": "user_message", "text": pending})
            await self.sender.send({"type": "status", "text": "正在打断并准备新指令...", "thinking": True})
        else:
            await self.sender.send({"type": "status", "text": "正在停止当前回复...", "thinking": True})
        try:
            await self.scheduler.interrupt(pending)
            self.session_state["busy"] = self.scheduler.busy
            self.session_state["interrupt_in_flight"] = self.scheduler.interrupt_in_flight
            if self.scheduler.pending_after_interrupt:
                self.session_state["pending_interrupt_text"] = self.scheduler.pending_after_interrupt
            else:
                self.session_state.pop("pending_interrupt_text", None)
            self.index.update_runtime_state(self.agent_session_id, status="interrupting")
            await self.send_session_list()
        except Exception as e:
            self.session_state["user_interrupt_requested"] = False
            self.scheduler.interrupt_in_flight = False
            self.session_state["interrupt_in_flight"] = False
            await self.sender.send({"type": "agent_text", "text": f"[错误] 打断失败: {e}"})
            await self.sender.send({"type": "status", "text": "打断失败，仍在等待当前回复...", "thinking": True})

    async def _receive_loop(self) -> None:
        assert self.client is not None
        assert self.log_file is not None
        assert self.scheduler is not None
        assert self.store is not None
        try:
            async for msg in self.client.receive_messages():
                _append_sdk_log_line(self.log_file, msg)
                self.scheduler.observe_message(msg)
                session_id = getattr(msg, "session_id", None)
                data = getattr(msg, "data", None)
                if not session_id and isinstance(data, dict):
                    session_id = data.get("session_id")
                if session_id:
                    self.index.update_runtime_state(
                        self.agent_session_id,
                        claude_session_id=str(session_id),
                    )
                persist_on_sdk_message(str(self.workspace), msg, self.session_state)
                if self.scheduler.pending_after_interrupt:
                    self.session_state["pending_interrupt_text"] = self.scheduler.pending_after_interrupt
                else:
                    self.session_state.pop("pending_interrupt_text", None)
                user_interrupted = bool(self.session_state.get("user_interrupt_requested"))
                await _dispatch_message_to_web(msg, self.sender, self.session_state)
                subtype = getattr(msg, "subtype", "") or ""
                if subtype in {"task_started", "task_notification", "task_updated"}:
                    await self.send_snapshot()
                if isinstance(msg, ResultMessage):
                    failed = result_message_indicates_failure(msg) and not user_interrupted
                    pending = self.scheduler.complete_result(msg, failed=failed)
                    self.session_state["busy"] = self.scheduler.busy
                    self.session_state["interrupt_in_flight"] = self.scheduler.interrupt_in_flight
                    self.session_state.pop("pending_interrupt_text", None)
                    self.index.update_runtime_state(
                        self.agent_session_id,
                        status="idle" if not failed else "error",
                    )
                    await self.send_session_list()
                    await self.send_snapshot()
                    if pending:
                        await self.sender.send(
                            {"type": "status", "text": "处理中断后的新指令...", "thinking": True}
                        )
                        write_user_turn_log(self.log_file, pending)
                        self.session_state["last_tool_error"] = False
                        await self.scheduler.submit(pending)
                        self.session_state["busy"] = self.scheduler.busy
                        self.index.update_runtime_state(self.agent_session_id, status="running")
                        await self.send_session_list()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.index.update_runtime_state(self.agent_session_id, status="error")
            await self.send_session_list()
            await self.sender.send({"type": "agent_text", "text": f"[错误] SDK 消息流异常: {e}"})
            raise


class WorkspaceRuntimeManager:
    def __init__(self, *, runs_root: Path, ui: Any, initial_workspace: Path) -> None:
        self.runs_root = runs_root.resolve()
        self.ui = ui
        self.index = WorkspaceSessionIndex(self.runs_root)
        self.index.sync_from_runs()
        initial = self.index.ensure_session_for_workspace(initial_workspace, title=initial_workspace.name)
        self.active_session_id = str(initial["agent_session_id"])
        self.runtimes: dict[str, WorkspaceRuntime] = {}

    async def start_initial(self) -> None:
        await self.open_runtime(self.active_session_id)

    async def close(self) -> None:
        for runtime in list(self.runtimes.values()):
            await runtime.close()
        self.index.close()

    async def open_runtime(self, agent_session_id: str) -> WorkspaceRuntime:
        runtime = self.runtimes.get(agent_session_id)
        if runtime:
            await runtime.start()
            return runtime
        record = self.index.get(agent_session_id)
        if not record:
            raise ValueError(f"unknown session: {agent_session_id}")
        runtime = WorkspaceRuntime(record=record, ui=self.ui, index=self.index)
        self.runtimes[agent_session_id] = runtime
        await runtime.start()
        return runtime

    async def on_connect(self, ui: Any, ws: Any) -> None:
        await self.send_session_list(ws=ws)
        await self.send_session_history(self.active_session_id, ws=ws)

    async def on_event(self, data: dict[str, Any]) -> None:
        event_type = str(data.get("type") or "")
        agent_session_id = str(data.get("agent_session_id") or self.active_session_id)

        if event_type == "create_session":
            title = str(data.get("title") or "").strip() or None
            record = self.index.create_session(title=title)
            self.active_session_id = str(record["agent_session_id"])
            await self.open_runtime(self.active_session_id)
            await self.send_session_list()
            await self.send_session_history(self.active_session_id)
            return

        if event_type == "select_session":
            if not self.index.get(agent_session_id):
                await self.ui.send({"type": "agent_text", "agent_session_id": self.active_session_id, "text": f"[错误] 未找到会话: {agent_session_id}"})
                return
            self.active_session_id = agent_session_id
            await self.open_runtime(agent_session_id)
            await self.send_session_list()
            await self.send_session_history(agent_session_id)
            return

        if event_type == "rename_session":
            title = str(data.get("title") or "").strip()
            self.index.rename(agent_session_id, title)
            await self.send_session_list()
            return

        if event_type == "star_session":
            self.index.set_starred(agent_session_id, bool(data.get("starred")))
            await self.send_session_list()
            return

        if event_type == "delete_session":
            await self.delete_session(agent_session_id, delete_files=bool(data.get("delete_files")))
            return

        if event_type == "stop_task":
            runtime = await self.open_runtime(agent_session_id)
            await runtime.stop_task(str(data.get("task_id") or ""))
            return

        if event_type in {"user_message", "interrupt"}:
            runtime = await self.open_runtime(agent_session_id)
            text = str(data.get("text") or "")
            if event_type == "interrupt":
                await runtime.handle_interrupt(text)
            else:
                await runtime.handle_user_message(text)
            await self.send_session_list()

    async def handle_api(self, action: str, request: Any) -> Any:
        if action == "list_sessions":
            return {"sessions": self.index.list_sessions(), "active_session_id": self.active_session_id}
        if action == "create_session":
            body = await request.json() if request.can_read_body else {}
            record = self.index.create_session(title=str(body.get("title") or "").strip() or None)
            self.active_session_id = str(record["agent_session_id"])
            await self.open_runtime(self.active_session_id)
            await self.send_session_list()
            return {"session": record, "active_session_id": self.active_session_id}
        if action == "update_session":
            agent_session_id = str(request.match_info["agent_session_id"])
            body = await request.json() if request.can_read_body else {}
            if "title" in body:
                self.index.rename(agent_session_id, str(body.get("title") or ""))
            if "starred" in body:
                self.index.set_starred(agent_session_id, bool(body.get("starred")))
            await self.send_session_list()
            return {"session": self.index.get(agent_session_id)}
        if action == "delete_session":
            agent_session_id = str(request.match_info["agent_session_id"])
            body = await request.json() if request.can_read_body else {}
            deleted = await self.delete_session(agent_session_id, delete_files=bool(body.get("delete_files")))
            return {"deleted": deleted, "active_session_id": self.active_session_id}
        return {"error": f"unknown action: {action}"}

    async def delete_session(self, agent_session_id: str, *, delete_files: bool = False) -> bool:
        runtime = self.runtimes.get(agent_session_id)
        if runtime and runtime.scheduler and runtime.scheduler.busy:
            await self.ui.send(
                {
                    "type": "agent_text",
                    "agent_session_id": agent_session_id,
                    "text": "[系统提示] 当前会话仍在运行，不能删除。请先停止当前回复或等待完成。",
                }
            )
            return False

        record = self.index.get(agent_session_id)
        if not record:
            await self.send_session_list()
            return False
        workspace = Path(record["workspace"]).resolve()

        if runtime:
            await runtime.close()
            self.runtimes.pop(agent_session_id, None)
        deleted = self.index.delete(agent_session_id)
        if not deleted:
            await self.send_session_list()
            return False

        if delete_files:
            try:
                workspace.relative_to(self.runs_root)
            except ValueError:
                await self.ui.send(
                    {
                        "type": "agent_text",
                        "agent_session_id": self.active_session_id,
                        "text": f"[错误] 拒绝删除 runs 目录外路径: {workspace}",
                    }
                )
                return False
            if workspace == self.runs_root:
                await self.ui.send(
                    {
                        "type": "agent_text",
                        "agent_session_id": self.active_session_id,
                        "text": "[错误] 拒绝删除 runs 根目录。",
                    }
                )
                return False
            shutil.rmtree(workspace, ignore_errors=False)

        sessions = self.index.list_sessions()
        if not sessions:
            new_record = self.index.create_session()
            sessions = [new_record]
        if self.active_session_id == agent_session_id:
            self.active_session_id = str(sessions[0]["agent_session_id"])
            await self.open_runtime(self.active_session_id)
            await self.send_session_history(self.active_session_id)
        await self.send_session_list()
        return True

    async def send_session_list(self, ws: Any | None = None) -> None:
        payload = {
            "type": "session_list",
            "sessions": self.index.list_sessions(),
            "active_session_id": self.active_session_id,
        }
        if ws is not None:
            await self.ui.send_to(ws, payload)
        else:
            await self.ui.send(payload)

    async def send_session_history(self, agent_session_id: str, ws: Any | None = None) -> None:
        record = self.index.get(agent_session_id)
        if not record:
            return
        runtime = self.runtimes.get(agent_session_id)
        events = runtime.history_events() if runtime else _with_session_id(
            parse_log_file_to_ui_events(
                Path(record["workspace"]) / SESSION_LOG_NAME,
                format_tool_result=_format_tool_result_content,
                result_failed=result_message_indicates_failure,
            ),
            agent_session_id,
        )
        tasks: list[dict[str, Any]] = []
        if runtime and runtime.store:
            tasks = _tasks_for_ui(runtime.store)
        payload = {
            "type": "session_history",
            "agent_session_id": agent_session_id,
            "events": events,
            "log_path": str(Path(record["workspace"]) / SESSION_LOG_NAME),
            "tasks": tasks,
        }
        if ws is not None:
            await self.ui.send_to(ws, payload)
        else:
            await self.ui.send(payload)


async def web_main(
    workspace: str,
    resume: str | None,
    log_append: bool,
    port: int = WEB_PORT,
    persist_context: str | None = None,
) -> None:
    from webui.web import WebUI

    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    manager_holder: dict[str, WorkspaceRuntimeManager] = {}

    async def _on_event(data: dict[str, Any]) -> None:
        await manager_holder["manager"].on_event(data)

    async def _on_connect(ui_obj: Any, ws_obj: Any) -> None:
        await manager_holder["manager"].on_connect(ui_obj, ws_obj)

    async def _api_handler(action: str, request: Any) -> Any:
        return await manager_holder["manager"].handle_api(action, request)

    ui = WebUI(
        port=port,
        on_event=_on_event,
        on_connect=_on_connect,
        api_handler=_api_handler,
    )
    manager = WorkspaceRuntimeManager(runs_root=RUNS_ROOT, ui=ui, initial_workspace=ws)
    manager_holder["manager"] = manager
    await ui.start()
    if ui.port != port:
        print(f"[web] 端口 {port} 已被占用，已改用 {ui.port}", flush=True)
    print(f"网页界面: http://localhost:{ui.port}")
    print(f"初始工作目录: {workspace}")
    if resume:
        print(f"恢复会话: {resume}（结构化状态或 log.txt）")
    else:
        print("新会话（无 resume 或 log 中无 session_id）")
    if persist_context:
        print(f"已注入本地持久化历史: {Path(workspace) / PERSIST_FILENAME}（约 {len(persist_context)} 字符）")
    print(f"会话索引: {RUNS_ROOT / '.scheduler' / 'session_index.sqlite3'}\n")
    try:
        try:
            await manager.start_initial()
            while True:
                await asyncio.sleep(3600)
        except ProcessError:
            _print_process_error_help(workspace, resume)
            raise
    finally:
        await manager.close()
        await ui.stop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VASP Agent")
    parser.add_argument(
        "--mode",
        choices=["cli", "web"],
        default="cli",
        help="交互模式：cli（终端，默认）或 web（网页）",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="",
        metavar="NAME",
        help=(
            "工作目录；省略则新建 runs/<时间戳>。"
            "传单级目录名时按 runs/<name> 解析；"
            "也支持相对路径或绝对路径。"
            "若目录内有 scheduler state 或 log.txt，则尝试恢复会话"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=WEB_PORT,
        metavar="N",
        help=f"网页端口（仅 web 模式，默认 {WEB_PORT}）",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        metavar="URL",
        help="LiteLLM（或其它 Anthropic 兼容服务）的 base URL；默认读 .env 中 BASE_URL（或 ANTHROPIC_BASE_URL），缺省为 http://127.0.0.1:4000",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        metavar="KEY",
        help="转发用的 API Key；默认读 .env 中 API_KEY（或 ANTHROPIC_API_KEY），可与 litellm 配置的 sk- 一致",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="仍使用 --dir 对应工作区，但不从 log.txt 恢复会话（用于 session 失效或调试）",
    )
    parser.add_argument(
        "--no-inject-persist",
        action="store_true",
        help="不从 conversation_turns.jsonl 注入历史到 system prompt（仍会继续写入该文件）",
    )
    parser.add_argument(
        "--no-litellm-autostart",
        action="store_true",
        help="不在本机端口未监听时自动 subprocess 启动 LiteLLM（需已手动启动代理）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    applied_url, _ = configure_anthropic_for_litellm(
        base_url=args.base_url,
        api_key=args.api_key,
    )
    applied_url, _ = maybe_prefer_direct_upstream(applied_url)
    maybe_start_litellm(applied_url, disable=args.no_litellm_autostart)
    final_llm_url = (os.environ.get("ANTHROPIC_BASE_URL") or applied_url).strip().rstrip("/")
    print(f"[llm] ANTHROPIC_BASE_URL={final_llm_url}", flush=True)
    try:
        ws_path, resume = resolve_workspace(args.dir)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)
    workspace_str = str(ws_path)
    log_append = bool(args.dir and str(args.dir).strip())
    if args.no_resume:
        resume = None

    persist_context: str | None = None
    if not args.no_inject_persist and resume is None:
        persist_context = load_persist_context_for_prompt(ws_path)

    if args.mode == "web":
        asyncio.run(
            web_main(workspace_str, resume, log_append, args.port, persist_context=persist_context),
        )
    else:
        asyncio.run(
            cli_main(workspace_str, resume, log_append, persist_context=persist_context),
        )


if __name__ == "__main__":
    main()
