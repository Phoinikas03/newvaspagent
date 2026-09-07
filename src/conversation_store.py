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
# 注入 system prompt 时的上限，从文件尾部向前截断。
#
# 必须按**字节**算，不能按字符：system prompt 是作为单个命令行参数传给 Claude Code
# CLI 的，Linux 对单参数有 MAX_ARG_STRLEN = 32 * PAGE_SIZE = 131072 字节的硬上限。
# 中文在 UTF-8 下 3 字节/字，此前按 120000 *字符* 截断，最坏情况就是 360 KB，
# 远超上限——恢复任何带中文历史的长会话都会在启动时 execve 失败（`[Errno 7]
# Argument list too long`），且报错发生在 SDK 内部，很难看出根因。
# 这里留足余量：基础 system prompt 约 28 KB，注入再占 64 KB，合计仍在上限内。
MAX_INJECT_BYTES = 64_000


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


def _blocks_from_event_log(workspace: Path | str) -> list[str]:
    """从 log.jsonl 派生对话文本。

    对话历史不再单独存一份文件——它是 log.jsonl 的视图。此前 log.txt 与
    conversation_turns.jsonl 双写，后者写失败会被静默吞掉，两者长期漂移。
    """
    from src.event_log import LOG_FILENAME, read_messages

    path = Path(workspace).resolve() / LOG_FILENAME
    if not path.is_file():
        return []

    blocks: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        buf.clear()
        if text:
            blocks.append(f"### Assistant\n{text}")

    for rec, msg in read_messages(path):
        rtype = rec.get("type")
        if rtype == "UserTurn":
            flush()
            text = ((rec.get("payload") or {}).get("text") or "").strip()
            if text:
                blocks.append(f"### User\n{text}")
        elif rtype == "AssistantMessage" and msg is not None:
            for block in getattr(msg, "content", []) or []:
                if type(block).__name__ == "TextBlock":
                    chunk = (getattr(block, "text", "") or "").strip()
                    if chunk:
                        buf.append(chunk)
        elif rtype == "ResultMessage":
            flush()
    flush()
    return blocks


def _blocks_from_legacy_store(workspace: Path | str) -> list[str]:
    """读旧的 conversation_turns.jsonl（仅用于尚未产生 log.jsonl 的历史工作区）。"""
    p = persist_path(workspace)
    if not p.is_file():
        return []
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    blocks: list[str] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
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
    return blocks


def load_persist_context_for_prompt(workspace: Path | str) -> str | None:
    """格式化为可注入 system prompt 的纯文本；过长时保留尾部。"""
    blocks = _blocks_from_event_log(workspace) or _blocks_from_legacy_store(workspace)
    if not blocks:
        return None
    out = "\n\n".join(blocks)
    encoded = out.encode("utf-8")
    if len(encoded) > MAX_INJECT_BYTES:
        # 从尾部取，再按 UTF-8 解码；截断点可能落在多字节字符中间，errors="ignore"
        # 丢掉开头那个残缺字符即可。
        out = encoded[-MAX_INJECT_BYTES:].decode("utf-8", errors="ignore")
        out = "…[前文已截断]…\n\n" + out
    return out


def persist_on_sdk_message(workspace: Path | str, msg: Any, state: dict[str, Any]) -> None:
    """保留为兼容占位：对话历史现在从 ``log.jsonl`` 派生，不再单独落盘。

    此前这里把助手文本累积后写进 ``conversation_turns.jsonl``，与 ``log.txt`` 双写。
    两者可能漂移，且助手文本只在 ``ResultMessage`` 时整轮落盘——中途崩溃就整轮丢失。
    ``log.jsonl`` 逐条即时写入，信息更全，派生视图见 ``_blocks_from_event_log``。
    """
    return
