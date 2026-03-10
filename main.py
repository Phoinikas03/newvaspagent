import os
import sys
import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import (
    create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient,
    AssistantMessage, ResultMessage, TextBlock,
)
from tool_wrapper import (
    poscar_tool, setup_vasp_inputs_tool, run_vasp_tool,
    duckduckgo_search_tool, google_search_tool, visit_webpage_tool, arxiv_search_tool,
)

load_dotenv(Path(__file__).parent / ".env")

os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:4000"
os.environ["ANTHROPIC_API_KEY"] = "sk-dummy-key"
os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"

LOG_DIR = Path(__file__).parent / "logs"
WORKSPACE = "/mnt/data_x3/xiazeyu/learn-claude-code/workspace"
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
        cwd=".",
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        system_prompt=(
            f"Your workspace directory is: {workspace}\n"
            f"All VASP input/output files should be read from and written to this directory.\n\n"
            f"CRITICAL CONSTRAINT: You MUST NOT call or attempt to use the `AskUserQuestion` tool. "
            f"If you need to ask the user a question, output it as plain text and stop generating.\n\n"
            f"SKILL IMPROVEMENT: When you have fully completed a task that involved using a SKILL, "
            f"proactively reflect on the execution trajectory. If the SKILL could be improved "
            f"(unclear steps, missing edge cases, potential errors), use simple-skill-creator to "
            f"update it and present the diff to the user for confirmation. "
            f"Only do this once the task is truly complete, not mid-task."
        ),
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

        print("思考中...", flush=True)
        await client.query(user_input)

        async for msg in client.receive_response():
            log_file.write(repr(msg) + "\n")
            log_file.flush()

            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(f"\nAgent> {block.text}", flush=True)
                    elif getattr(block, "type", None) == "tool_use":
                        tool_name = getattr(block, "name", "?")
                        try:
                            input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                        except Exception:
                            input_str = str(getattr(block, "input", ""))
                        print(f"\n[工具调用] {tool_name}\n{input_str}", flush=True)

            elif isinstance(msg, ResultMessage):
                status = "✓ 完成" if not msg.is_error else "✗ 出错"
                print(f"\n{status}  轮次: {msg.num_turns}\n", flush=True)


async def cli_main() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    print(f"VASP Agent (CLI 模式)  |  输入 quit 或 exit 退出")
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

            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        await ui.send({"type": "agent_text", "text": block.text})
                    elif getattr(block, "type", None) == "tool_use":
                        try:
                            input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                        except Exception:
                            input_str = str(getattr(block, "input", ""))
                        await ui.send({"type": "tool_use", "name": getattr(block, "name", "?"), "input_str": input_str})

            elif isinstance(msg, ResultMessage):
                await ui.send({"type": "result", "turns": msg.num_turns, "error": msg.is_error})
                await ui.send({"type": "status", "text": "就绪", "thinking": False})
                await ui.send({"type": "done"})


async def web_main() -> None:
    from web import WebUI

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    ui = WebUI(port=WEB_PORT)
    await ui.start()
    print(f"网页界面: http://localhost:{WEB_PORT}")
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
