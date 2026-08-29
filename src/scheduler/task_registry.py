from __future__ import annotations

import hashlib
from typing import Any

from .state_store import SchedulerStateStore

TERMINAL_TASK_STATUSES = {"completed", "failed", "stopped", "cancelled", "canceled", "killed"}


def _message_data(msg: Any) -> dict[str, Any]:
    data = getattr(msg, "data", None)
    return data if isinstance(data, dict) else {}


def _message_subtype(msg: Any) -> str:
    return str(getattr(msg, "subtype", "") or "")


def _message_session_id(msg: Any) -> str | None:
    data = _message_data(msg)
    session_id = getattr(msg, "session_id", None) or data.get("session_id")
    return str(session_id) if session_id else None


def _status_for(subtype: str, data: dict[str, Any], previous: str | None = None) -> str:
    """推断任务状态。

    此前在缺 status 字段时返回 ``"updated"`` / ``"notification"``，这两个都不在
    ``TERMINAL_TASK_STATUSES`` 里，导致任务永远不会终结，``/running-tasks`` 和
    界面的任务面板会永久堆积僵尸条目。现在没有明确状态时沿用上一次的状态，
    只有真正拿到 status 才改变它。
    """
    patch = data.get("patch") if isinstance(data.get("patch"), dict) else {}
    status = data.get("status") or patch.get("status")
    if status:
        return str(status)
    if subtype == "task_started":
        return "running"
    if previous:
        return previous
    return "running" if subtype == "task_updated" else "notification"


def _task_label(subtype: str, data: dict[str, Any]) -> str:
    for key in ("summary", "description", "label", "name", "output_file"):
        value = data.get(key)
        if value:
            return str(value)
    patch = data.get("patch") if isinstance(data.get("patch"), dict) else {}
    if patch.get("status"):
        return f"{subtype}: {patch['status']}"
    return subtype


class TaskRegistry:
    """Tracks Claude Code background-task messages in the scheduler store."""

    TASK_SUBTYPES = {"task_started", "task_notification", "task_updated"}

    def __init__(self, store: SchedulerStateStore) -> None:
        self.store = store

    def observe_message(self, msg: Any, *, turn_id: str | None = None) -> dict[str, Any] | None:
        subtype = _message_subtype(msg)
        data = _message_data(msg)
        session_id = _message_session_id(msg)
        if session_id:
            self.store.save_claude_session_id(session_id, source=f"message:{subtype or type(msg).__name__}")
        if subtype not in self.TASK_SUBTYPES:
            return None

        raw_task_id = (
            getattr(msg, "task_id", None)
            or data.get("task_id")
            or data.get("taskId")
            or data.get("id")
        )
        label = _task_label(subtype, data)
        if raw_task_id:
            task_id = str(raw_task_id)
        else:
            # 兜底 id 只能用同一任务生命周期内**不变**的量。此前把 subtype 和
            # label 也算进摘要，而两者都随 task_started → task_updated 变化，
            # 于是同一个任务在表里裂成多行，首尾永远关联不上。
            tool_use_id = getattr(msg, "tool_use_id", None) or data.get("tool_use_id")
            anchor = str(tool_use_id) if tool_use_id else f"turn:{turn_id}"
            digest = hashlib.sha1(
                f"{self.store.scheduler_session_id}:{anchor}".encode("utf-8")
            ).hexdigest()[:12]
            task_id = f"claude:{digest}"

        existing = self.store.get_task(task_id)
        status = _status_for(subtype, data, previous=(existing or {}).get("status"))
        self.store.upsert_task(
            task_id=task_id,
            kind="claude",
            status=status,
            label=label,
            owner="claude-code",
            turn_id=turn_id,
            # data 按 subtype 分槽存放，避免每次更新把上一次的 data 整个覆盖掉，
            # 那样 task_started 的启动信息会在第一次 update 后就消失。
            metadata={"subtype": subtype, f"data_{subtype}": data},
        )
        self.store.record_event(
            "task.claude.updated",
            text=label,
            payload={"task_id": task_id, "status": status, "subtype": subtype},
            turn_id=turn_id,
        )
        return {"task_id": task_id, "status": status, "label": label, "kind": "claude"}


def format_task_list(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "暂无已记录任务。"

    lines = ["任务列表：", "ID | 类型 | 状态 | 描述", "--- | --- | --- | ---"]
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        kind = str(task.get("kind", ""))
        status = str(task.get("status", ""))
        label = str(task.get("label", "")).replace("\n", " ")
        if len(label) > 90:
            label = label[:87] + "..."
        lines.append(f"`{task_id}` | {kind} | {status} | {label}")
    return "\n".join(lines)
