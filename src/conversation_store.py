"""
工作区内持久化对话轮次（JSONL），用于在无 Claude Code ``resume`` 时向 system prompt 注入历史，实现「新开会话也能接着聊」。

文件：``<workspace>/conversation_turns.jsonl``，每行一条 JSON：``role``（user|assistant）、``text``、``ts``（ISO8601 UTC）。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PERSIST_FILENAME = "conversation_turns.jsonl"
# 注入 system prompt 时的上限（字符），从文件尾部向前截断
MAX_INJECT_CHARS = 120_000


def persist_path(workspace: Path | str) -> Path:
    return Path(workspace).resolve() / PERSIST_FILENAME


def append_turn(workspace: Path | str, role: str, text: str) -> None:
    text = (text or "").strip()
    if not text or role not in ("user", "assistant"):
        return
    p = persist_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "role": role,
        "text": text,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_persist_context_for_prompt(workspace: Path | str) -> str | None:
    """读取 JSONL，格式化为可注入的纯文本；过长时保留尾部。"""
    p = persist_path(workspace)
    if not p.is_file():
        return None
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return None
    blocks: list[str] = []
    for ln in lines:
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        role = o.get("role")
        text = (o.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            blocks.append(f"### User\n{text}")
        elif role == "assistant":
            blocks.append(f"### Assistant\n{text}")
    if not blocks:
        return None
    out = "\n\n".join(blocks)
    if len(out) > MAX_INJECT_CHARS:
        out = out[-MAX_INJECT_CHARS:]
        out = "…[前文已截断]…\n\n" + out
    return out


def persist_on_sdk_message(workspace: Path | str, msg: Any, state: dict[str, Any]) -> None:
    """
    在 SDK 消息流中累积 Assistant 文本，在 ResultMessage 时落盘一行 assistant。
    User 侧在 ``write_user_turn_log`` 中写入。
    """
    from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

    ws = Path(workspace).resolve()

    if isinstance(msg, AssistantMessage):
        parts: list[str] = []
        for block in getattr(msg, "content", []):
            if type(block).__name__ == "TextBlock" or isinstance(block, TextBlock):
                parts.append(block.text)
        if parts:
            chunk = "\n".join(parts).strip()
            if chunk:
                buf = state.get("persist_assistant_buf", "")
                state["persist_assistant_buf"] = (buf + "\n" + chunk).strip() if buf else chunk
        return

    if isinstance(msg, ResultMessage):
        buf = (state.get("persist_assistant_buf") or "").strip()
        state["persist_assistant_buf"] = ""
        if buf:
            append_turn(ws, "assistant", buf)
