"""从 log.txt 恢复网页端展示用事件流；并记录用户输入行以便完整对话历史。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

# 与 log 中其它行区分：单行 JSON
USER_LOG_KEY = "_vasp_agent_user"


def write_user_turn_log(log_file, text: str) -> None:
    """在发起 query 前写入一行，便于网页重载后还原「用户说了什么」。"""
    line = json.dumps({USER_LOG_KEY: "user", "text": text}, ensure_ascii=False)
    log_file.write(line + "\n")
    log_file.flush()


def _format_tool_result_content(content: Any) -> str:
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


def _eval_sdk_message(line: str) -> Any | None:
    """将 log 中单行 repr 还原为 SDK 消息对象。"""
    ns = {
        "AssistantMessage": AssistantMessage,
        "UserMessage": UserMessage,
        "ResultMessage": ResultMessage,
        "SystemMessage": SystemMessage,
        "TextBlock": TextBlock,
        "ThinkingBlock": ThinkingBlock,
        "ToolUseBlock": ToolUseBlock,
        "ToolResultBlock": ToolResultBlock,
    }
    line = line.strip()
    if not line:
        return None
    if line.startswith("StreamEvent"):
        return None
    if line.startswith("SystemMessage"):
        return None
    try:
        return eval(line, {"__builtins__": {}}, ns)
    except Exception:
        return None


def sdk_message_to_ui_events(
    msg: Any,
    *,
    format_tool_result: Callable[[Any], str],
    result_failed: Callable[[Any], bool],
) -> list[dict[str, Any]]:
    """与 web_agent_loop 一致，将单条 SDK 消息转为前端事件列表（不含 status/done）。"""
    events: list[dict[str, Any]] = []
    msg_type = type(msg).__name__

    if msg_type == "AssistantMessage" or isinstance(msg, AssistantMessage):
        for block in getattr(msg, "content", []):
            bt = type(block).__name__
            if bt == "TextBlock" or isinstance(block, TextBlock):
                events.append({"type": "agent_text", "text": block.text})
            elif bt == "ThinkingBlock" or isinstance(block, ThinkingBlock):
                events.append(
                    {"type": "agent_text", "text": "[思考]\n" + getattr(block, "thinking", "")}
                )
            elif bt == "ToolUseBlock" or getattr(block, "type", None) == "tool_use":
                try:
                    input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                except Exception:
                    input_str = str(getattr(block, "input", ""))
                events.append(
                    {
                        "type": "tool_use",
                        "name": getattr(block, "name", "?"),
                        "input_str": input_str,
                    }
                )

    elif msg_type == "UserMessage" or isinstance(msg, UserMessage):
        raw = getattr(msg, "content", None)
        blocks = raw if isinstance(raw, list) else []
        for block in blocks:
            if isinstance(block, ToolResultBlock):
                tid = getattr(block, "tool_use_id", "") or ""
                err = getattr(block, "is_error", None)
                is_err = bool(err) if err is not None else False
                body = format_tool_result(getattr(block, "content", None))
                events.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "is_error": is_err,
                        "content_str": body,
                    }
                )
            elif isinstance(block, TextBlock):
                events.append({"type": "agent_text", "text": "[上下文]\n" + block.text})

    elif msg_type == "ResultMessage" or isinstance(msg, ResultMessage):
        failed = result_failed(msg)
        events.append(
            {
                "type": "result",
                "turns": getattr(msg, "num_turns", 0),
                "error": failed,
                "subtype": getattr(msg, "subtype", None) or "",
                "summary": getattr(msg, "result", None) or "",
            }
        )

    return events


def parse_log_file_to_ui_events(
    log_path: Path,
    *,
    format_tool_result: Callable[[Any], str] | None = None,
    result_failed: Callable[[Any], bool] | None = None,
) -> list[dict[str, Any]]:
    """
    解析 log.txt：用户行（JSON）+ SDK repr 行，生成与 WebSocket 协议一致的事件列表。
    """
    fmt = format_tool_result or _format_tool_result_content
    if result_failed is None:
        from result_message import result_message_indicates_failure

        result_failed = result_message_indicates_failure

    if not log_path.is_file():
        return []

    events: list[dict[str, Any]] = []
    try:
        f = log_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return []

    with f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict) and obj.get(USER_LOG_KEY) == "user":
                events.append({"type": "user_message", "text": obj.get("text", "")})
                continue

            msg = _eval_sdk_message(line)
            if msg is None:
                continue
            events.extend(
                sdk_message_to_ui_events(msg, format_tool_result=fmt, result_failed=result_failed)
            )

    return events
