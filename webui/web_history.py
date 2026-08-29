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
        # 右侧 Todo 栏应该展示任务名本身，而不是「已完成/待完成/进行中」这类状态短语。
        # activeForm 仍可用于状态栏，但面板标签优先使用 content。
        label = (t.get("content") or t.get("activeForm") or "").strip()
        if not label:
            continue
        if len(label) > TODO_LABEL_MAX_LEN:
            label = label[: TODO_LABEL_MAX_LEN - 1] + "…"
        out.append({"label": label, "status": status})
    return out


#: Skill 正文注入的识别特征。CLI 措辞变化时这里会失配，后果是整份 SKILL.md
#: 以明文灌进聊天流（而这恰恰是蒸馏最想精确识别的一段），所以列多个候选并
#: 补一个结构性兜底，而不是只认一个前缀。
_SKILL_INJECTION_PREFIXES = (
    "Base directory for this skill:",
    "Base directory for skill:",
)


def is_skill_injection_context_text(text: str) -> bool:
    """判断一段 UserMessage/TextBlock 是否为 Skill 工具注入的 SKILL.md 正文。

    Skill 工具除 ToolResultBlock 外，还会单独注入整份 SKILL.md。
    """
    if not text or not isinstance(text, str):
        return False
    head = text.lstrip()
    if head.startswith(_SKILL_INJECTION_PREFIXES):
        return True
    # 结构性兜底：首行提到 skill 的目录/路径，且正文带 YAML frontmatter。
    first_line, _, rest = head.partition("\n")
    if len(first_line) < 200 and "skill" in first_line.lower():
        if ":" in first_line and rest.lstrip().startswith("---"):
            return True
    return False


def write_user_turn_log(log_writer, text: str, *, turn_id: str | None = None) -> None:
    """在发起 query 前写入一行，便于网页重载后还原「用户说了什么」。

    历史上这里要双写 log.txt 和 conversation_turns.jsonl，两者可能漂移（后者写失败
    会被静默吞掉）。现在只写 log.jsonl，助手/用户文本由它统一派生。
    """
    log_writer.append_user_turn(text, turn_id=turn_id)


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
    """将旧 log.txt 中单行 repr 还原为 SDK 消息对象。

    命名空间取 SDK 全部 dataclass 类型。此前硬编码 8 个类名，导致
    ``TaskStartedMessage`` / ``TaskNotificationMessage`` 等解析失败后被静默丢弃——
    实测历史日志中有 502 条后台任务消息因此在重放里消失。
    """
    from src.event_log import SDK_TYPES

    line = line.strip()
    if not line:
        return None
    if line.startswith("StreamEvent"):
        return None
    try:
        return eval(line, {"__builtins__": {}}, SDK_TYPES)  # noqa: S307 - 受控命名空间
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

    # 后台任务消息：重放必须与实时显示一致，否则刷新页面后 VASP 长任务的
    # 启停记录会整段消失（见 src/main.py 的 _dispatch_message_to_web）。
    subtype = getattr(msg, "subtype", "") or ""
    if subtype in {"task_notification", "task_started", "task_updated"}:
        data = getattr(msg, "data", None)
        data = data if isinstance(data, dict) else {}
        if subtype == "task_notification":
            summary = data.get("summary") or ""
            if summary:
                events.append({"type": "agent_text", "text": f"[后台任务] {summary}"})
        elif subtype == "task_started":
            desc = data.get("description") or ""
            if desc:
                events.append({"type": "agent_text", "text": f"[后台任务] 已启动: {desc}"})
        else:
            task_id = data.get("task_id") or ""
            patch = data.get("patch") if isinstance(data.get("patch"), dict) else {}
            status = patch.get("status") or data.get("status") or "updated"
            events.append({"type": "agent_text", "text": f"[后台任务] {task_id} {status}"})
        return events
    if msg_type == "SystemMessage":
        return events

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
    """解析会话日志，生成与 WebSocket 协议一致的事件列表。

    ``log.jsonl`` 走结构化路径；尚未迁移的旧 ``log.txt`` 仍按原来的
    「用户行 JSON + SDK repr 行」解析，保证历史会话可回放。
    """
    fmt = format_tool_result or _format_tool_result_content
    if result_failed is None:
        from src.result_message import result_message_indicates_failure

        result_failed = result_message_indicates_failure

    if not log_path.is_file():
        return []

    events: list[dict[str, Any]] = []

    if log_path.name.endswith(".jsonl"):
        from src.event_log import read_messages

        for rec, msg in read_messages(log_path):
            if rec.get("type") == "UserTurn":
                text = (rec.get("payload") or {}).get("text", "")
                events.append({"type": "user_message", "text": str(text)})
                continue
            if msg is None:
                continue
            events.extend(
                sdk_message_to_ui_events(msg, format_tool_result=fmt, result_failed=result_failed)
            )
        return _prepend_replay_notice_if_needed(events)

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
