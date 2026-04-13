import os
import re
import sys
import asyncio
import argparse
import json
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
    poscar_tool, setup_vasp_inputs_tool,
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
from src.litellm_env import configure_anthropic_for_litellm
from src.conversation_store import PERSIST_FILENAME, load_persist_context_for_prompt, persist_on_sdk_message
from src.litellm_autostart import maybe_start_litellm

load_dotenv(REPO_ROOT / ".env")

SESSION_LOG_NAME = "log.txt"
CLAUDE_STDERR_LOG = "claude_stderr.log"
WEB_PORT = 8888
RUNS_ROOT = REPO_ROOT / "runs"

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
    - run_dir 非空：使用 runs/<run_dir>，若存在 log.txt 则解析 session_id 供 SDK resume。
    """
    base = RUNS_ROOT.resolve()
    name = (run_dir or "").strip()
    if not name:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ws = base / ts
        ws.mkdir(parents=True, exist_ok=True)
        return ws, None
    if name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError("--dir 只能是 runs 下的单级子目录名，不能含路径分隔符")
    ws = (base / name).resolve()
    try:
        ws.relative_to(base)
    except ValueError:
        raise ValueError("--dir 解析后不在 runs 目录内")
    if not ws.is_dir():
        raise ValueError(f"目录不存在: {ws}")
    resume = _parse_last_session_id(ws / SESSION_LOG_NAME)
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
            poscar_tool(workspace),
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

    return ClaudeAgentOptions(
        cwd=workspace,
        resume=resume,
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        stderr=_cli_stderr,
        system_prompt=f"""Your workspace directory is: {workspace}
All VASP input/output files should be read from and written to this directory.

Repository root (skills, `.claude`, and all paths documented in SKILL files): {repo_root}
The shell cwd for Bash is the **session workspace** above, which is **not** the repository root. Paths like `.claude/skills/...` are relative to **{repo_root}**, not to the workspace.

SKILL & `.claude` PATH RULE (mandatory):
- Any Bash that loads or runs skill assets (Python scripts under `.claude/skills/`, `vasp_runner.py`, `probe_env.py`, `quick_test.py`, sourcing templates, etc.) MUST start by changing directory to the repository root: prefix with `cd "{repo_root}" && ...`, **or** use absolute paths beginning with `{repo_root}/`.
- Do **not** assume `.claude` exists under the session workspace.

VASP FILE PROVENANCE (mandatory): You MUST NOT use Write, Edit, or Bash/heredocs to manually author the full contents of **POSCAR**, **POTCAR**, or **KPOINTS**. Obtain crystal structures only through **`get_poscar_from_md`** (or other retrieval tools such as search + documented procedures—not by typing lattice vectors and coordinates from memory). Generate **POTCAR** (and the POSCAR copy used with them in the workspace) **only** via **`setup_vasp_inputs`**. Prefer **KSPACING** (and optionally **KGAMMA**) in **INCAR** so **`setup_vasp_inputs`** does not create a **KPOINTS** file; only when **KSPACING** is absent does the tool write **KPOINTS** from density. You MAY create or adjust **INCAR** by copying skill templates and changing parameters (ENCUT, ISMEAR, KSPACING, etc.).

CRITICAL INTERACTION RULE: You MUST NOT call or attempt to use the `AskUserQuestion` tool. Instead, whenever you finish a major workflow step, encounter an error, or need permission to proceed to a computationally expensive task (like running VASP), you MUST output a plain text block. In this text block, clearly summarize what you have achieved so far, and explicitly ask the user for confirmation to proceed to the next step. NEVER terminate your turn silently without reporting your status.

END OF TURN & ANTI-SILENCE REQUIREMENT (CRITICAL):
You are STRICTLY FORBIDDEN from ending a conversation turn silently.
1. The LAST THING the user sees in your turn MUST ALWAYS be ordinary human-readable text (Chinese or English prose; Markdown allowed).
2. If your last action was a tool call (especially if the tool returned an ERROR, 'Exit code 1', or empty output), you MUST explicitly generate a text block analyzing the result or explaining the failure before waiting for the user.
3. Never end a turn with only tool calls, empty text, placeholder or control tokens (e.g. strings like "<ctrl46>" or similar), or meaningless repeated characters. If you are stuck, explicitly say (in the user's language when appropriate): "我遇到了问题，需要您的帮助..." and describe the roadblock.

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

VASP ORCHESTRATION & PRE-CHECK (INTELLIGENT DISCOVERY & STRICT ALIGNMENT):
Before starting any actual VASP computation, you MUST act as an intelligent orchestrator. You MUST NOT blindly execute VASP without following these steps:

1. Identify intent: Is this a Quick Test (e.g., checking INCAR/convergence) or a Production run?
2. Proactively Probe: **Prefer** the `run_vasp` skill's `scripts/probe_env.py` — invoke with Bash, obeying SKILL & `.claude` PATH RULE, e.g. `cd "{repo_root}" && python .claude/skills/run_vasp/scripts/probe_env.py` (reports CPU, GPU, and scheduler using `sbatch` / `qsub` in PATH—no `sinfo` required). If you supplement with Bash:
   - CPU: `lscpu`
   - GPU: `nvidia-smi -L` (ignore if missing)
   - Workload managers: treat Slurm as present if `sbatch` is in PATH, PBS if `qsub` is in PATH. Run `sinfo` or `qstat` **only** after `command -v sinfo` / `command -v qstat` succeeds; on bare-metal workstations these are often absent and **must not** fail the probe.
   - Node: `hostname`
   **Never** chain `lscpu`, `nvidia-smi`, and optional `sinfo`/`qstat` with `&&` in one command—if `sinfo` is missing, the entire command fails (exit 127) and can break parallel tool batches.
3. STRICT HARDWARE ALIGNMENT (Mandatory Query):
   - If BOTH GPUs AND CPUs are detected, you MUST NOT default to CPU execution. You MUST stop and explicitly ask the user: "I detected both GPUs and CPUs. Do you prefer to use GPU acceleration (e.g., vasp_gpu) or CPU only? If GPU, how many?"
   - If a Workload Manager (Slurm/PBS) is detected, you MUST NOT run locally. You MUST explicitly ask the user for cluster-specific parameters: "Please provide the target partition/queue name, number of nodes, and time limit for the job script."
4. Confirm Strategy: After gathering user preferences, present the final execution strategy (e.g., exact mpirun command with GPU bindings, or the exact sbatch script) for explicit confirmation before triggering the computation. NEVER execute heavy `mpirun` commands directly if a login node is detected.

TASK MONITORING RULE: For local, time-consuming commands (like a local VASP run), use the `TaskOutput` tool with `block=True` to wait for the task to finish, keeping the workflow automated. However, if submitting a job via a workload manager (like SLURM/PBS), DO NOT block indefinitely on the submission command. Instead, submit the job, capture the Job ID, and use appropriate commands (e.g., `squeue`) to monitor the status, informing the user of the queued/running state before concluding your turn.

ITERATIVE EXECUTION RULE: When performing parameter sweeps or convergence tests, DO NOT write and execute monolithic Python/Bash scripts containing loops to run VASP multiple times. Instead, you MUST manage the loop logically in your own reasoning and run VASP for EACH data point ONE BY ONE (via Bash / TaskOutput / workload manager as directed by the `run_vasp` skill and orchestration rules above). This allows for intermediate checks and prevents unmanageable background processes.

POTCAR SELECTION RULE: When selecting pseudopotentials (POTCARs), if multiple versions exist for an element (e.g., standard, `_pv`, `_sv`), ALWAYS prioritize the standard version with the FEWEST valence electrons (usually the one without suffixes) to minimize computational cost, unless higher accuracy semi-core states are strictly requested.
{persist_block}""",
        mcp_servers={mcp_name: mcp_server},
        allowed_tools=[
            "Skill",
            f"mcp__{mcp_name}__get_poscar_from_md",
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

    if isinstance(msg, SystemMessage):
        if msg.subtype == "task_notification":
            summary = (msg.data or {}).get("summary") or ""
            if summary:
                print(f"[后台任务] {summary}\n", flush=True)
        elif msg.subtype == "task_started":
            desc = (msg.data or {}).get("description") or ""
            if desc:
                print(f"[后台任务] 已启动: {desc}\n", flush=True)
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
) -> None:
    """持续消费 SDK 消息流（ClaudeSDKClient.receive_messages）。

    与 receive_response()（在 ResultMessage 处结束）不同：空闲等待用户输入时仍可收到
    SystemMessage（如 task_notification），从而及时写入 log 与终端。
    """
    async for msg in client.receive_messages():
        _append_sdk_log_line(log_file, msg)
        persist_on_sdk_message(workspace, msg, persist_state)
        _dispatch_message_to_cli(msg)


async def cli_agent_loop(
    client: ClaudeSDKClient,
    log_file,
    workspace: str,
) -> None:
    persist_state: dict[str, Any] = {"persist_assistant_buf": ""}
    drain = asyncio.create_task(_cli_sdk_receive_loop(client, log_file, workspace, persist_state))
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

            print("思考中...\n", flush=True)
            write_user_turn_log(log_file, user_input)
            await client.query(user_input)
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
        print(f"恢复会话: {resume}（自 log.txt 解析）")
    else:
        print("新会话（无 resume 或 log 中无 session_id）")
    if persist_context:
        print(f"已注入本地持久化历史: {Path(workspace) / PERSIST_FILENAME}（约 {len(persist_context)} 字符）")
    print(f"日志写入: {log_path}（{'追加' if log_append else '新建'}）\n")

    log_mode = "a" if log_append else "w"
    log_file = open(log_path, log_mode, encoding="utf-8")
    try:
        try:
            async with ClaudeSDKClient(
                options=build_options(workspace, resume=resume, persist_context=persist_context),
            ) as client:
                await cli_agent_loop(client, log_file, workspace)
        except ProcessError:
            _print_process_error_help(workspace, resume)
            raise
    finally:
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

    if isinstance(msg, SystemMessage):
        data = msg.data or {}
        if msg.subtype == "task_notification":
            summary = data.get("summary") or ""
            if summary:
                await ui.send({"type": "agent_text", "text": f"[后台任务] {summary}"})
        elif msg.subtype == "task_started":
            desc = data.get("description") or ""
            if desc:
                await ui.send({"type": "agent_text", "text": f"[后台任务] 已启动: {desc}"})
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
        result_text = (getattr(msg, "result", None) or "").strip()
        if session_state is not None and not result_text and session_state.get("last_tool_error"):
            await ui.send({"type": "agent_text", "text": EMPTY_RESULT_WITH_TOOL_ERROR_FALLBACK})
        if session_state is not None:
            session_state["last_tool_error"] = False
        failed = result_message_indicates_failure(msg)
        await ui.send({
            "type": "result",
            "turns": getattr(msg, "num_turns", 0),
            "error": failed,
            "subtype": getattr(msg, "subtype", None) or "",
            "summary": getattr(msg, "result", None) or "",
        })
        await ui.send({"type": "status", "text": "就绪 — 请在下方输入", "thinking": False})
        await ui.send({"type": "done"})


async def _web_sdk_receive_loop(
    client: ClaudeSDKClient,
    log_file,
    ui: Any,
    session_state: dict[str, Any],
    workspace: str,
) -> None:
    """后台持续 consume receive_messages()，与主协程中仅负责 query(用户输入) 分离。"""
    try:
        async for msg in client.receive_messages():
            _append_sdk_log_line(log_file, msg)
            persist_on_sdk_message(workspace, msg, session_state)
            await _dispatch_message_to_web(msg, ui, session_state)
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
) -> None:
    drain = asyncio.create_task(
        _web_sdk_receive_loop(client, log_file, ui, session_state, workspace),
    )
    try:
        while True:
            user_input = await ui.input_queue.get()
            if user_input.lower() in ("quit", "exit"):
                break

            await ui.send({"type": "status", "text": "思考中...", "thinking": True})
            write_user_turn_log(log_file, user_input)
            session_state["last_tool_error"] = False
            await client.query(user_input)
    finally:
        drain.cancel()
        with suppress(asyncio.CancelledError):
            await drain


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
    log_path = ws / SESSION_LOG_NAME

    prior_events = parse_log_file_to_ui_events(
        log_path,
        format_tool_result=_format_tool_result_content,
        result_failed=result_message_indicates_failure,
    )
    ui = WebUI(port=port)
    ui.extend_history(prior_events)
    await ui.start()
    print(f"网页界面: http://localhost:{port}")
    print(f"工作目录: {workspace}")
    if resume:
        print(f"恢复会话: {resume}")
    else:
        print("新会话（无 resume 或 log 中无 session_id）")
    if persist_context:
        print(f"已注入本地持久化历史: {Path(workspace) / PERSIST_FILENAME}（约 {len(persist_context)} 字符）")
    print(f"日志写入: {log_path}（{'追加' if log_append else '新建'}）\n")

    log_mode = "a" if log_append else "w"
    log_file = open(log_path, log_mode, encoding="utf-8")
    try:
        try:
            async with ClaudeSDKClient(
                options=build_options(workspace, resume=resume, persist_context=persist_context),
            ) as client:
                async def _notify_log():
                    while ui._ws is None:
                        await asyncio.sleep(0.5)
                    await ui.send({"type": "log_path", "path": str(log_path)})
                asyncio.create_task(_notify_log())

                web_session_state: dict[str, Any] = {
                    "last_tool_error": False,
                    "persist_assistant_buf": "",
                }
                await web_agent_loop(client, log_file, ui, web_session_state, workspace)
        except ProcessError:
            _print_process_error_help(workspace, resume)
            raise
    finally:
        log_file.close()
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
        help="runs 下的子目录名；省略或空则新建时间戳目录并开始新会话；指定则使用该目录并尝试从 log.txt 恢复会话",
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
    print(f"[llm] ANTHROPIC_BASE_URL={applied_url}", flush=True)
    maybe_start_litellm(applied_url, disable=args.no_litellm_autostart)
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