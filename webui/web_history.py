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

# TodoWrite 的 activeForm/content 可能很长，状态栏截断以免撑破布局
TODO_STATUS_MAX_LEN = 120


def todo_write_in_progress_label(tool_input: Any) -> str | None:
    """
    从 TodoWrite 的 input 中取出当前 in_progress 项的简短说明，用于 Web 状态栏与 log 重放。
    解决：模型在长回合里先写了「第一步」正文，随后已开始 surface/absorbed，但正文未更新时界面看起来像卡在第一步。
    """
    if not isinstance(tool_input, dict):
        return None
    todos = tool_input.get("todos")
    if not isinstance(todos, list):
        return None
    for t in todos:
        if not isinstance(t, dict):
            continue
        if t.get("status") != "in_progress":
            continue
        label = (t.get("activeForm") or t.get("content") or "").strip()
        if not label:
            continue
        if len(label) > TODO_STATUS_MAX_LEN:
            label = label[: TODO_STATUS_MAX_LEN - 1] + "…"
        return label
    return None


_VALID_TODO_STATUSES = frozenset({"completed", "in_progress", "pending"})
TODO_LABEL_MAX_LEN = 200


def todo_write_items_for_ui(tool_input: Any) -> list[dict[str, str]]:
    """
    将 TodoWrite 的 input 转为右侧 Todo 栏用的结构化列表。
    每项: {"label": str, "status": "completed"|"in_progress"|"pending"}
    """
    out: list[dict[str, str]] = []
    if not isinstance(tool_input, dict):
        return out
    todos = tool_input.get("todos")
    if not isinstance(todos, list):
        return out
    for t in todos:
        if not isinstance(t, dict):
            continue
        raw = t.get("status")
        status = raw if raw in _VALID_TODO_STATUSES else "pending"
        label = (t.get("activeForm") or t.get("content") or "").strip()
        if not label:
            continue
        if len(label) > TODO_LABEL_MAX_LEN:
            label = label[: TODO_LABEL_MAX_LEN - 1] + "…"
        out.append({"label": label, "status": status})
    return out


def is_skill_injection_context_text(text: str) -> bool:
    """
    Skill 工具除 ToolResultBlock 外，还会在单独的 UserMessage/TextBlock 里注入整份 SKILL.md。
    正文通常以「Base directory for this skill:」开头（与 CLI Skill 加载一致）。
    """
    if not text or not isinstance(text, str):
        return False
    return text.lstrip().startswith("Base directory for this skill:")


def write_user_turn_log(log_file, text: str) -> None:
    """在发起 query 前写入一行，便于网页重载后还原「用户说了什么」。"""
    line = json.dumps({USER_LOG_KEY: "user", "text": text}, ensure_ascii=False)
    log_file.write(line + "\n")
    log_file.flush()
    try:
        from src.conversation_store import append_turn

        append_turn(Path(log_file.name).parent, "user", text)
    except OSError:
        pass


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
                tname = getattr(block, "name", "?")
                tid = getattr(block, "id", "") or ""
                try:
                    input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                except Exception:
                    input_str = str(getattr(block, "input", ""))
                events.append(
                    {
                        "type": "tool_use",
                        "name": tname,
                        "input_str": input_str,
                        "tool_use_id": tid,
                    }
                )
                if tname == "TodoWrite":
                    tw_in = getattr(block, "input", None) or {}
                    events.append(
                        {
                            "type": "todo_update",
                            "todos": todo_write_items_for_ui(tw_in),
                        }
                    )
                    label = todo_write_in_progress_label(tw_in)
                    if label:
                        events.append(
                            {
                                "type": "status",
                                "text": f"进行中: {label}",
                                "thinking": True,
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
                if is_skill_injection_context_text(block.text):
                    events.append(
                        {
                            "type": "agent_text",
                            "text": block.text,
                            "collapsed": True,
                            "collapsed_label": "Skill 正文（点击展开）",
                        }
                    )
                else:
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


def _prepend_replay_notice_if_needed(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """若 log 中无用户行或前半段缺用户行，在重放列表前加一条说明，避免误以为网页坏了。"""
    if not events:
        return events
    has_user = any(e.get("type") == "user_message" for e in events)
    if not has_user:
        notice = {
            "type": "agent_text",
            "text": (
                "⚠️ **提示**：本 log.txt 中**没有**记录用户输入行（`_vasp_agent_user`），"
                "无法显示「You」气泡。当前版本会在每轮对话前写入该行；**继续本会话后**新产生的输入会出现在记录与重放中。"
            ),
        }
        return [notice] + events
    if events[0].get("type") != "user_message":
        notice = {
            "type": "agent_text",
            "text": (
                "⚠️ **提示**：本记录**前半段**缺少用户输入行（旧版或未写入），"
                "故开头几轮不会显示「You」；后文若出现用户气泡，为当时已启用记录后的对话。"
            ),
        }
        return [notice] + events
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
        from src.result_message import result_message_indicates_failure

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
            # 与 write_user_turn_log 一致；放宽为「含 _vasp_agent_user 与 text」即可解析
            if isinstance(obj, dict) and USER_LOG_KEY in obj and "text" in obj:
                events.append({"type": "user_message", "text": str(obj.get("text", ""))})
                continue

            msg = _eval_sdk_message(line)
            if msg is None:
                continue
            events.extend(
                sdk_message_to_ui_events(
                    msg,
                    format_tool_result=fmt,
                    result_failed=result_failed,
                )
            )

    return _prepend_replay_notice_if_needed(events)
