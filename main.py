import os
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient, AssistantMessage, ResultMessage, TextBlock
from tool_wrapper import poscar_tool, setup_vasp_inputs_tool, run_vasp_tool, duckduckgo_search_tool, google_search_tool, visit_webpage_tool, arxiv_search_tool

load_dotenv(Path(__file__).parent / ".env")

os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:4000"
os.environ["ANTHROPIC_API_KEY"] = "sk-dummy-key"
os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"

LOG_DIR = Path(__file__).parent / "logs"


def open_log() -> tuple[Path, object]:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    return log_path, open(log_path, "w", encoding="utf-8")


async def main():
    workspace = "/mnt/data_x3/xiazeyu/learn-claude-code/workspace"
    mcp_server_name = "vasp_agent"
    mcp_server = create_sdk_mcp_server(
        name=mcp_server_name,
        tools=[
            poscar_tool(workspace),
            setup_vasp_inputs_tool(workspace),
            run_vasp_tool(workspace),
            duckduckgo_search_tool(),
            google_search_tool(),
            visit_webpage_tool(),
            arxiv_search_tool(),
        ]
    )

    options = ClaudeAgentOptions(
        cwd='.',
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        system_prompt = (
            f"Your workspace directory is: {workspace}\n"
            f"All VASP input/output files should be read from and written to this directory.\n\n"
            f"CRITICAL CONSTRAINT: You are running in a headless CLI Python script environment without a GUI frontend. "
            f"Therefore, you MUST NOT call or attempt to use the `AskUserQuestion` tool under any circumstances. "
            f"If you need to ask the user a question (e.g., to confirm parameters or check structure relaxation), "
            f"simply output the question in plain text at the end of your response and stop generating. "
            f"The user will answer via standard console input."
        ),
        mcp_servers={mcp_server_name: mcp_server},
        allowed_tools=[
            "Skill",
            f"mcp__{mcp_server_name}__get_poscar_from_md",
            f"mcp__{mcp_server_name}__setup_vasp_inputs",
            f"mcp__{mcp_server_name}__run_vasp",
            f"mcp__{mcp_server_name}__duckduckgo_search",
            f"mcp__{mcp_server_name}__google_search",
            f"mcp__{mcp_server_name}__visit_webpage",
            f"mcp__{mcp_server_name}__arxiv_search",
        ]
    )

    log_path, log_file = open_log()
    print(f"日志写入：{log_path}\n")

    try:
        async with ClaudeSDKClient(options=options) as client:
            print("VASP Agent 已启动。输入 'quit' 或 'exit' 退出。\n")
            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n已退出。")
                    break
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit"):
                    print("已退出。")
                    break

                await client.query(user_input)
                async for msg in client.receive_response():
                    log_file.write(repr(msg) + "\n")
                    log_file.flush()
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                print(f"Agent: {block.text}")
                    elif isinstance(msg, ResultMessage):
                        if msg.is_error:
                            print(f"[错误] turns={msg.num_turns}")
                        else:
                            print(f"[完成] turns={msg.num_turns}")
                        print()
    finally:
        log_file.close()

if __name__ == "__main__":
    asyncio.run(main())