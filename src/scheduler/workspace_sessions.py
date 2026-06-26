from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .state_store import SCHEDULER_DIR_NAME, load_structured_resume_session_id, utc_now


SESSION_INDEX_DIR = SCHEDULER_DIR_NAME
SESSION_INDEX_DB = "session_index.sqlite3"


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    value = value.strip(".-")
    return value[:80] or datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_last_session_id(log_path: Path) -> str | None:
    if not log_path.is_file():
        return None
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    matches = re.findall(
        r"session_id='([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'",
        text,
    )
    return matches[-1] if matches else None


class WorkspaceSessionIndex:
    """Global index of VASP Agent workspace sessions under ``runs/``."""

    def __init__(self, runs_root: str | Path) -> None:
        self.runs_root = Path(runs_root).resolve()
        self.index_dir = self.runs_root / SESSION_INDEX_DIR
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / SESSION_INDEX_DB
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            create table if not exists workspace_sessions (
                agent_session_id text primary key,
                title text not null,
                workspace text not null unique,
                claude_session_id text,
                status text not null default 'idle',
                starred integer not null default 0,
                created_at text not null,
                updated_at text not null,
                last_opened_at text,
                metadata_json text not null default '{}'
            );
            """
        )
        self.conn.commit()

    def sync_from_runs(self) -> None:
        if not self.runs_root.is_dir():
            return
        for child in sorted(self.runs_root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if not ((child / "log.txt").exists() or (child / SCHEDULER_DIR_NAME).exists()):
                continue
            self.ensure_session_for_workspace(child, title=child.name, touch=False)

    def ensure_session_for_workspace(
        self,
        workspace: str | Path,
        *,
        title: str | None = None,
        touch: bool = True,
    ) -> dict[str, Any]:
        ws = Path(workspace).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        row = self.conn.execute(
            "select * from workspace_sessions where workspace = ?",
            (str(ws),),
        ).fetchone()
        if row:
            if touch:
                self.touch(str(row["agent_session_id"]))
            return self._row_to_dict(row)

        base_id = _slug(ws.name)
        agent_session_id = self._unique_session_id(base_id, workspace=ws)
        now = utc_now()
        claude_session_id = load_structured_resume_session_id(ws) or _parse_last_session_id(ws / "log.txt")
        self.conn.execute(
            """
            insert into workspace_sessions
            (agent_session_id, title, workspace, claude_session_id, status, starred,
             created_at, updated_at, last_opened_at, metadata_json)
            values (?, ?, ?, ?, 'idle', 0, ?, ?, ?, '{}')
            """,
            (
                agent_session_id,
                title or ws.name,
                str(ws),
                claude_session_id,
                now,
                now,
                now if touch else None,
            ),
        )
        self.conn.commit()
        return self.get(agent_session_id) or {}

    def create_session(self, title: str | None = None) -> dict[str, Any]:
        now_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        title = (title or now_name).strip() or now_name
        base = _slug(title)
        agent_session_id = self._unique_session_id(base)
        workspace = self.runs_root / agent_session_id
        workspace.mkdir(parents=True, exist_ok=True)
        now = utc_now()
        self.conn.execute(
            """
            insert into workspace_sessions
            (agent_session_id, title, workspace, status, starred, created_at, updated_at, last_opened_at, metadata_json)
            values (?, ?, ?, 'idle', 0, ?, ?, ?, '{}')
            """,
            (agent_session_id, title, str(workspace.resolve()), now, now, now),
        )
        self.conn.commit()
        return self.get(agent_session_id) or {}

    def list_sessions(self) -> list[dict[str, Any]]:
        self.sync_from_runs()
        rows = self.conn.execute(
            """
            select * from workspace_sessions
             order by starred desc, coalesce(last_opened_at, updated_at) desc, title collate nocase asc
            """
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get(self, agent_session_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "select * from workspace_sessions where agent_session_id = ?",
            (agent_session_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def touch(self, agent_session_id: str) -> None:
        self.conn.execute(
            "update workspace_sessions set last_opened_at = ?, updated_at = ? where agent_session_id = ?",
            (utc_now(), utc_now(), agent_session_id),
        )
        self.conn.commit()

    def rename(self, agent_session_id: str, title: str) -> dict[str, Any] | None:
        title = title.strip()
        if not title:
            return self.get(agent_session_id)
        self.conn.execute(
            "update workspace_sessions set title = ?, updated_at = ? where agent_session_id = ?",
            (title[:120], utc_now(), agent_session_id),
        )
        self.conn.commit()
        return self.get(agent_session_id)

    def set_starred(self, agent_session_id: str, starred: bool) -> dict[str, Any] | None:
        self.conn.execute(
            "update workspace_sessions set starred = ?, updated_at = ? where agent_session_id = ?",
            (1 if starred else 0, utc_now(), agent_session_id),
        )
        self.conn.commit()
        return self.get(agent_session_id)

    def update_runtime_state(
        self,
        agent_session_id: str,
        *,
        status: str | None = None,
        claude_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        row = self.get(agent_session_id)
        if not row:
            return None
        old_meta = dict(row.get("metadata") or {})
        if metadata:
            old_meta.update(metadata)
        self.conn.execute(
            """
            update workspace_sessions
               set status = coalesce(?, status),
                   claude_session_id = coalesce(?, claude_session_id),
                   metadata_json = ?,
                   updated_at = ?
             where agent_session_id = ?
            """,
            (
                status,
                claude_session_id,
                json.dumps(old_meta, ensure_ascii=False),
                utc_now(),
                agent_session_id,
            ),
        )
        self.conn.commit()
        return self.get(agent_session_id)

    def _unique_session_id(self, base: str, workspace: Path | None = None) -> str:
        candidate = base
        suffix = 2
        while True:
            row = self.conn.execute(
                "select workspace from workspace_sessions where agent_session_id = ?",
                (candidate,),
            ).fetchone()
            if not row:
                return candidate
            if workspace and Path(row["workspace"]).resolve() == workspace.resolve():
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["starred"] = bool(data.get("starred"))
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
        return data
