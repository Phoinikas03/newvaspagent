import os
import asyncio
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
from web import WebUI

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
            f"If you need to ask the user a question, output it as plain text and stop generating."
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


async def agent_loop(client: ClaudeSDKClient, log_file, ui: WebUI) -> None:
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


async def main() -> None:
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

            await agent_loop(client, log_file, ui)
    finally:
        log_file.close()
        await ui.stop()


if __name__ == "__main__":
    asyncio.run(main())
