from __future__ import annotations

import inspect
import shlex
import uuid
from dataclasses import dataclass
from typing import Any

from .state_store import SchedulerStateStore
from .task_registry import TERMINAL_TASK_STATUSES, TaskRegistry, format_task_list


@dataclass
class ControlResponse:
    handled: bool
    text: str = ""
    thinking: bool = False
    done: bool = True


class AgentScheduler:
    """Thin runtime controller around ClaudeSDKClient.

    It does not replace Claude Code. It keeps host-side state and routes
    user-level controls through one place so CLI and WebUI behave consistently.
    """

    def __init__(self, client: Any, store: SchedulerStateStore, tasks: TaskRegistry) -> None:
        self.client = client
        self.store = store
        self.tasks = tasks
        self.busy = False
        self.interrupt_in_flight = False
        self.current_turn_id: str | None = None
        self.pending_after_interrupt: str | None = None

    async def submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self.busy:
            await self.interrupt(pending_text=text)
            return
        turn_id = str(uuid.uuid4())
        self.current_turn_id = turn_id
        self.pending_after_interrupt = None
        self.busy = True
        self.store.start_turn(turn_id, text)
        await self.client.query(text)

    async def interrupt(self, pending_text: str | None = None) -> None:
        pending = (pending_text or "").strip()
        if pending:
            self.pending_after_interrupt = pending
        if not self.busy:
            if pending:
                await self.submit(pending)
            return
        if self.interrupt_in_flight:
            return
        self.interrupt_in_flight = True
        self.store.record_event(
            "control.interrupt",
            text="interrupt current Claude turn",
            payload={"has_pending_text": bool(pending)},
            turn_id=self.current_turn_id,
        )
        await self.client.interrupt()

    def observe_message(self, msg: Any) -> None:
        session_id = self._extract_session_id(msg)
        if session_id:
            self.store.save_claude_session_id(session_id, source=f"message:{type(msg).__name__}")
        self.tasks.observe_message(msg, turn_id=self.current_turn_id)

    def complete_result(self, msg: Any, *, failed: bool) -> str:
        session_id = self._extract_session_id(msg)
        if session_id:
            self.store.save_claude_session_id(session_id, source="result")
        if self.current_turn_id:
            payload = {
                "subtype": getattr(msg, "subtype", None),
                "num_turns": getattr(msg, "num_turns", None),
                "session_id": session_id,
                "result": getattr(msg, "result", None),
            }
            self.store.finish_turn(
                self.current_turn_id,
                "failed" if failed else "completed",
                payload,
            )
        self.busy = False
        self.interrupt_in_flight = False
        self.current_turn_id = None
        pending = (self.pending_after_interrupt or "").strip()
        self.pending_after_interrupt = None
        return pending

    async def handle_control_command(self, text: str, *, allow_interrupt: bool = False) -> ControlResponse:
        stripped = text.strip()
        if not stripped.startswith("/"):
            return ControlResponse(False)
        try:
            parts = shlex.split(stripped)
        except ValueError as exc:
            return ControlResponse(True, f"调度命令解析失败: {exc}")
        if not parts:
            return ControlResponse(False)

        command = parts[0].lower()
        if command in {"/scheduler-help", "/scheduler"}:
            return ControlResponse(True, self._help_text())
        if command == "/tasks":
            return ControlResponse(True, format_task_list(self.store.list_tasks(include_terminal=True)))
        if command == "/running-tasks":
            return ControlResponse(True, format_task_list(self.store.list_tasks(include_terminal=False)))
        if command == "/interrupt":
            if not allow_interrupt:
                return ControlResponse(False)
            await self.interrupt()
            return ControlResponse(True, "已向 Claude Code 发送 interrupt。", thinking=self.busy, done=not self.busy)
        if command == "/stop-claude-task":
            if len(parts) != 2:
                return ControlResponse(True, "用法: /stop-claude-task <task_id>")
            return await self._stop_claude_task(parts[1])
        if command == "/stop-vasp-task":
            if len(parts) != 2:
                return ControlResponse(True, "用法: /stop-vasp-task <task_id>")
            return self._stop_vasp_task(parts[1])
        return ControlResponse(False)

    async def _stop_claude_task(self, task_id: str) -> ControlResponse:
        task = self.store.get_task(task_id)
        if not task:
            return ControlResponse(True, f"未找到 Claude task: {task_id}")
        if task.get("kind") != "claude":
            return ControlResponse(True, f"任务 `{task_id}` 类型是 `{task.get('kind')}`，不是 Claude task。")
        if str(task.get("status", "")).lower() in TERMINAL_TASK_STATUSES:
            return ControlResponse(True, f"任务 `{task_id}` 已处于 `{task.get('status')}` 状态。")

        stop_task = getattr(self.client, "stop_task", None)
        if not callable(stop_task):
            self.store.record_event(
                "control.stop_claude_task.unsupported",
                text="ClaudeSDKClient has no stop_task method",
                payload={"task_id": task_id},
                turn_id=self.current_turn_id,
            )
            return ControlResponse(
                True,
                (
                    "当前安装的 claude-agent-sdk 只暴露 `interrupt()`，"
                    "没有宿主可直接调用的 `stop_task()`；因此不能像 Claude Code 原生 UI 那样"
                    f"实时停止子任务 `{task_id}`。可以先 `/interrupt` 当前 turn，"
                    "再让 agent 使用 Claude Code 的 `TaskStop` 工具处理该 task。"
                ),
            )

        result = stop_task(task_id)
        if inspect.isawaitable(result):
            await result
        self.store.mark_task_status(task_id, "stopped", metadata={"stop_reason": "scheduler command"})
        self.store.record_event(
            "control.stop_claude_task",
            text=f"stopped Claude task {task_id}",
            payload={"task_id": task_id},
            turn_id=self.current_turn_id,
        )
        return ControlResponse(True, f"已请求停止 Claude task `{task_id}`。")

    def _stop_vasp_task(self, task_id: str) -> ControlResponse:
        task = self.store.get_task(task_id)
        if not task:
            return ControlResponse(True, f"未找到 VASP task: {task_id}")
        if task.get("kind") != "vasp":
            return ControlResponse(True, f"任务 `{task_id}` 类型是 `{task.get('kind')}`，不是 VASP task。")
        self.store.record_event(
            "control.stop_vasp_task.refused",
            text="VASP termination requires state-backed runner metadata",
            payload={"task_id": task_id},
            turn_id=self.current_turn_id,
        )
        return ControlResponse(
            True,
            (
                "VASP 任务终止必须走 `.claude/skills/run_vasp/scripts/terminate.py` "
                "和精确 work-dir/job-id 证据；当前调度层还没有从 vasp_runner 接收"
                f"任务 `{task_id}` 的 state-backed 元数据，因此拒绝执行停止。"
            ),
        )

    def _extract_session_id(self, msg: Any) -> str | None:
        session_id = getattr(msg, "session_id", None)
        data = getattr(msg, "data", None)
        if not session_id and isinstance(data, dict):
            session_id = data.get("session_id")
        return str(session_id) if session_id else None

    def _help_text(self) -> str:
        return (
            "调度命令:\n"
            "- `/tasks` 查看已记录任务\n"
            "- `/running-tasks` 只看非终态任务\n"
            "- `/interrupt` 打断当前 Claude turn（CLI 可用，Web 按停止按钮更自然）\n"
            "- `/stop-claude-task <task_id>` 尝试停止 Claude Code 后台 task（取决于 SDK 是否暴露 stop_task）\n"
            "- `/stop-vasp-task <task_id>` 预留给 state-backed VASP runner，未满足证据时拒绝终止"
        )
