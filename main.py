import os
import sys
import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from typing import Any

from claude_agent_sdk import (
    create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient,
    AssistantMessage, ResultMessage, TextBlock,
    ToolResultBlock, UserMessage,
)
from tool_wrapper import (
    poscar_tool, setup_vasp_inputs_tool, run_vasp_tool,
    duckduckgo_search_tool, google_search_tool, visit_webpage_tool, arxiv_search_tool,
)

load_dotenv(Path(__file__).parent / ".env")

os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:4000"
os.environ["ANTHROPIC_API_KEY"] = "sk-dummy-key"
os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"

# 1. 在全局生成统一的启动时间戳
RUN_TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')

# 2. 将 WORKSPACE 设定为带有时间戳的子目录；会话日志固定为 WORKSPACE/log.txt
WORKSPACE = f"/mnt/data_x3/xiazeyu/newvaspagent/runs/{RUN_TIMESTAMP}"
SESSION_LOG_NAME = "log.txt"
WEB_PORT = 8888


def build_options(workspace: str) -> ClaudeAgentOptions:
    mcp_name = "vasp_agent"
    mcp_server = create_sdk_mcp_server(
        name=mcp_name,
        tools=[
            poscar_tool(workspace),
            setup_vasp_inputs_tool(workspace),
            run_vasp_tool(workspace),
            duckduckgo_search_tool(),
            google_search_tool(),
            visit_webpage_tool(),
            arxiv_search_tool(),
        ],
    )
    return ClaudeAgentOptions(
        cwd=workspace,
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        system_prompt=f"""Your workspace directory is: {workspace}
All VASP input/output files should be read from and written to this directory.

VASP FILE PROVENANCE (mandatory): You MUST NOT use Write, Edit, or Bash/heredocs to manually author the full contents of **POSCAR**, **POTCAR**, or **KPOINTS**. Obtain crystal structures only through **`get_poscar_from_md`** (or other retrieval tools such as search + documented procedures—not by typing lattice vectors and coordinates from memory). Generate **POTCAR** and **KPOINTS** (and the POSCAR copy used with them in the workspace) **only** via **`setup_vasp_inputs`**. You MAY create or adjust **INCAR** by copying skill templates and changing parameters (ENCUT, ISMEAR, etc.); that is allowed because INCAR is parameter text, not pseudopotential or k-mesh data.

CRITICAL INTERACTION RULE: You MUST NOT call or attempt to use the `AskUserQuestion` tool. Instead, whenever you finish a major workflow step, encounter an error, or need permission to proceed to a computationally expensive task (like running VASP), you MUST output a plain text block. In this text block, clearly summarize what you have achieved so far, and explicitly ask the user for confirmation to proceed to the next step. NEVER terminate your turn silently without reporting your status.

END OF TURN REQUIREMENT: Before you finish any conversation turn (i.e., before you stop generating and wait for the user's next input), you MUST output a plain text message. This message must summarize what was just completed and explicitly provide the user with the next steps, options, or a direct question. You are strictly forbidden from ending a turn silently.

FINAL VISIBLE OUTPUT (anti-empty summary): The last content the user sees in your turn MUST be ordinary human-readable prose (Markdown allowed). You MUST NOT end a turn with only: tool calls and no text; empty text; placeholder or control tokens (e.g. strings like "<ctrl46>" or similar); or meaningless repeated characters. After the last tool result you act on, you MUST still output a short closing summary in natural language (Chinese or English) listing what was done (key files, commands, or VASP steps), current status, and what happens next or what you need from the user.

SKILL IMPROVEMENT: When you have fully completed a task that involved using a SKILL, proactively reflect on the execution trajectory. If the SKILL could be improved (unclear steps, missing edge cases, potential errors), use simple-skill-creator to update it and present the diff to the user for confirmation. Only do this once the task is truly complete, not mid-task.

CRITICAL: If you encounter 'command not found' or 'ModuleNotFoundError' while following a SKILL, 
DO NOT attempt to use generic 'Read' tools on binary files (like PDF). 
Instead, report the missing dependency to the user and ask for instructions.

VASP ORCHESTRATION & PRE-CHECK (INTELLIGENT DISCOVERY): Before starting any actual VASP computation, you MUST NOT blindly ask the user for configuration details. Instead, you MUST act as an intelligent orchestrator:
1. Identify intent: Is this a Quick Test (e.g., checking INCAR/convergence) or a Production run?
2. Proactively Probe: Use available Bash tools or probe scripts to detect the hardware and environment (e.g., presence of Slurm/PBS, is it a login node?, CPU core count via `lscpu`, GPU availability via `nvidia-smi`).
3. Formulate Strategy: Based on the probe, design a scheduling strategy (e.g., using `sbatch` for login nodes, explicit GPU binding for multi-gpu workstations, or partitioning CPU cores for fat nodes). 
4. Confirm Strategy: Present this specific strategy (local vs. slurm, node/core/GPU allocation) to the user for explicit confirmation. NEVER execute heavy `mpirun` commands directly if a login node is detected.

TASK MONITORING RULE: For local, time-consuming commands (like a local VASP run), use the `TaskOutput` tool with `block=True` to wait for the task to finish, keeping the workflow automated. However, if submitting a job via a workload manager (like SLURM/PBS), DO NOT block indefinitely on the submission command. Instead, submit the job, capture the Job ID, and use appropriate commands (e.g., `squeue`) to monitor the status, informing the user of the queued/running state before concluding your turn.

ITERATIVE EXECUTION RULE: When performing parameter sweeps or convergence tests, DO NOT write and execute monolithic Python/Bash scripts containing loops to run VASP multiple times. Instead, you MUST manage the loop logically in your own reasoning and call the VASP execution tools for EACH data point ONE BY ONE. This allows for intermediate checks and prevents unmanageable background processes.

POTCAR SELECTION RULE: When selecting pseudopotentials (POTCARs), if multiple versions exist for an element (e.g., standard, `_pv`, `_sv`), ALWAYS prioritize the standard version with the FEWEST valence electrons (usually the one without suffixes) to minimize computational cost, unless higher accuracy semi-core states are strictly requested.
""",
        mcp_servers={mcp_name: mcp_server},
        allowed_tools=[
            "Skill",
            f"mcp__{mcp_name}__get_poscar_from_md",
            f"mcp__{mcp_name}__setup_vasp_inputs",
            f"mcp__{mcp_name}__run_vasp",
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


async def cli_agent_loop(client: ClaudeSDKClient, log_file) -> None:
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
        await client.query(user_input)

        async for msg in client.receive_response():
            log_file.write(repr(msg) + "\n")
            log_file.flush()

            # 使用类型名称匹配，提高稳健性，捕捉工具调用和结果
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" or isinstance(msg, AssistantMessage):
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

            elif msg_type == "UserMessage":
                for block in getattr(msg, "content", []):
                    if type(block).__name__ == "ToolResultBlock":
                        content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)
                        status_icon = "❌" if is_error else "✅"
                        
                        content_str = str(content)
                        if len(content_str) > 300:
                            content_str = content_str[:300] + "\n ... [内容已截断]"
                            
                        print(f" [{status_icon} 工具返回结果]\n {content_str}\n", flush=True)

            elif msg_type == "ResultMessage" or isinstance(msg, ResultMessage):
                status = "✓ 完成" if not msg.is_error else "✗ 出错"
                print(f"\n{status}  轮次: {msg.num_turns}\n", flush=True)


async def cli_main() -> None:
    ws = Path(WORKSPACE)
    ws.mkdir(parents=True, exist_ok=True)
    log_path = ws / SESSION_LOG_NAME

    print(f"VASP Agent (CLI 模式)  |  输入 quit 或 exit 退出")
    print(f"工作目录: {WORKSPACE}")
    print(f"日志写入: {log_path}\n")

    log_file = open(log_path, "w", encoding="utf-8")
    try:
        async with ClaudeSDKClient(options=build_options(WORKSPACE)) as client:
            await cli_agent_loop(client, log_file)
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


async def web_agent_loop(client: ClaudeSDKClient, log_file, ui) -> None:
    while True:
        user_input = await ui.input_queue.get()
        if user_input.lower() in ("quit", "exit"):
            break

        await ui.send({"type": "status", "text": "思考中...", "thinking": True})
        await client.query(user_input)

        async for msg in client.receive_response():
            log_file.write(repr(msg) + "\n")
            log_file.flush()
            print(repr(msg))

            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" or isinstance(msg, AssistantMessage):
                for block in getattr(msg, "content", []):
                    block_type = type(block).__name__
                    
                    if block_type == "TextBlock" or isinstance(block, TextBlock):
                        await ui.send({"type": "agent_text", "text": block.text})
                    elif block_type == "ToolUseBlock" or getattr(block, "type", None) == "tool_use":
                        try:
                            input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                        except Exception:
                            input_str = str(getattr(block, "input", ""))
                        await ui.send({"type": "tool_use", "name": getattr(block, "name", "?"), "input_str": input_str})

            elif msg_type == "UserMessage" or isinstance(msg, UserMessage):
                raw = getattr(msg, "content", None)
                blocks = raw if isinstance(raw, list) else []
                for block in blocks:
                    if not isinstance(block, ToolResultBlock):
                        continue
                    tid = getattr(block, "tool_use_id", "") or ""
                    err = getattr(block, "is_error", None)
                    is_err = bool(err) if err is not None else False
                    body = _format_tool_result_content(getattr(block, "content", None))
                    await ui.send(
                        {
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "is_error": is_err,
                            "content_str": body,
                        }
                    )

            elif msg_type == "ResultMessage" or isinstance(msg, ResultMessage):
                await ui.send({
                    "type": "result",
                    "turns": getattr(msg, "num_turns", 0),
                    "error": getattr(msg, "is_error", False),
                    # SDK 汇总的最终文本；网页端流式 TextBlock 若因 Markdown 解析失败未显示，可依赖此项
                    "summary": getattr(msg, "result", None) or "",
                })
                # 明确提示可继续输入，避免用户误以为在 ResultMessage 后「卡住」
                await ui.send({"type": "status", "text": "就绪 — 请在下方输入", "thinking": False})
                await ui.send({"type": "done"})


async def web_main() -> None:
    from web import WebUI

    ws = Path(WORKSPACE)
    ws.mkdir(parents=True, exist_ok=True)
    log_path = ws / SESSION_LOG_NAME

    ui = WebUI(port=WEB_PORT)
    await ui.start()
    print(f"网页界面: http://localhost:{WEB_PORT}")
    print(f"工作目录: {WORKSPACE}")
    print(f"日志写入: {log_path}\n")

    log_file = open(log_path, "w", encoding="utf-8")
    try:
        async with ClaudeSDKClient(options=build_options(WORKSPACE)) as client:
            async def _notify_log():
                while ui._ws is None:
                    await asyncio.sleep(0.5)
                await ui.send({"type": "log_path", "path": str(log_path)})
            asyncio.create_task(_notify_log())

            await web_agent_loop(client, log_file, ui)
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "web":
        asyncio.run(web_main())
    else:
        asyncio.run(cli_main())