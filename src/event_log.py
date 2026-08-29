"""结构化会话日志 ``log.jsonl``：写入、读取、以及从旧 ``log.txt`` 的无损转换。

替代原先并存的两个文件：

- ``log.txt``    —— 每行 ``repr(SDK消息)``，靠 ``eval`` 读回，类型白名单外的消息会被静默丢弃
- ``conversation_turns.jsonl`` —— ``log.txt`` 的派生视图（user/assistant 纯文本 + 时间戳）

新格式每行一条 JSON：

``{"v":1,"seq":int,"ts":"...","type":"AssistantMessage","session_id":...,
   "turn_id":...,"payload":{...}}``

关键约定：``payload`` 里每个嵌套 dataclass 都带 ``__type__``。不能靠字段签名反推类型——
``ServerToolUseBlock`` 与 ``ToolUseBlock`` 的字段完全相同（``id``/``input``/``name``），
猜类型必然撞车。
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import claude_agent_sdk.types as _sdk_types

LOG_FILENAME = "log.jsonl"
LEGACY_LOG_FILENAME = "log.txt"
SCHEMA_VERSION = 1

#: SDK 中全部 dataclass 类型。用于序列化打标与从 repr 还原，避免硬编码白名单——
#: 原实现只列了 8 个类名，SDK 新增消息类型时会被静默丢弃。
SDK_TYPES: dict[str, type] = {
    name: obj
    for name, obj in vars(_sdk_types).items()
    if inspect.isclass(obj) and dataclasses.is_dataclass(obj)
}

TYPE_KEY = "__type__"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# --------------------------------------------------------------------------
# 序列化
# --------------------------------------------------------------------------

def encode(obj: Any) -> Any:
    """递归转为可 JSON 序列化的结构，并给每个 dataclass 打上 ``__type__``。"""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out: dict[str, Any] = {TYPE_KEY: type(obj).__name__}
        for f in dataclasses.fields(obj):
            out[f.name] = encode(getattr(obj, f.name))
        return out
    if isinstance(obj, dict):
        return {str(k): encode(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [encode(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)  # datetime、Path 等兜底为字符串，保证永不因序列化失败丢行


def decode(value: Any) -> Any:
    """``encode`` 的逆操作。未知 ``__type__`` 保留为普通 dict，不丢数据。"""
    if isinstance(value, dict):
        tname = value.get(TYPE_KEY)
        payload = {k: decode(v) for k, v in value.items() if k != TYPE_KEY}
        cls = SDK_TYPES.get(tname) if tname else None
        if cls is None:
            return payload if tname is None else {TYPE_KEY: tname, **payload}
        known = {f.name for f in dataclasses.fields(cls)}
        try:
            return cls(**{k: v for k, v in payload.items() if k in known})
        except Exception:
            return {TYPE_KEY: tname, **payload}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def _extract_session_id(msg: Any) -> str | None:
    sid = getattr(msg, "session_id", None)
    if not sid:
        data = getattr(msg, "data", None)
        if isinstance(data, dict):
            sid = data.get("session_id")
    return str(sid) if sid else None


# --------------------------------------------------------------------------
# 写入
# --------------------------------------------------------------------------

class EventLogWriter:
    """``log.jsonl`` 的追加写入器。持有一个长期打开的句柄，每条 flush。"""

    def __init__(self, path: Path | str, *, start_seq: int = 0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = start_seq
        self._fh = self.path.open("a", encoding="utf-8")

    @classmethod
    def open_for_workspace(cls, workspace: Path | str) -> "EventLogWriter":
        p = Path(workspace) / LOG_FILENAME
        return cls(p, start_seq=_last_seq(p))

    def _write(self, record: dict[str, Any]) -> None:
        self._seq += 1
        record["seq"] = self._seq
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def append_sdk_message(self, msg: Any, *, turn_id: str | None = None) -> None:
        self._write(
            {
                "v": SCHEMA_VERSION,
                "ts": _now(),
                "type": type(msg).__name__,
                "session_id": _extract_session_id(msg),
                "turn_id": turn_id,
                "payload": encode(msg),
            }
        )

    def append_user_turn(self, text: str, *, turn_id: str | None = None) -> None:
        self._write(
            {
                "v": SCHEMA_VERSION,
                "ts": _now(),
                "type": "UserTurn",
                "session_id": None,
                "turn_id": turn_id,
                "payload": {"role": "user", "text": text},
            }
        )

    def close(self) -> None:
        try:
            self._fh.close()
        except OSError:
            pass


def find_workspace_root(start: Path | str) -> Path | None:
    """从任务目录向上找到含 ``log.jsonl`` 的工作区根。

    VASP 的每个算例各有自己的子目录（EOS 体积点、吸附三段式），而日志是
    每工作区一份，所以外部进程需要先定位到根。
    """
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if (candidate / LOG_FILENAME).is_file():
            return candidate
        if (candidate / "runs").is_dir() and candidate.name != "runs":
            break  # 已走到仓库根，不再上溯
    return None


def append_external_record(
    workspace: Path | str,
    *,
    type: str,
    payload: dict[str, Any],
) -> bool:
    """由 agent 会话之外的进程追加一条记录（如 vasp_runner 的运行生命周期）。

    与 :class:`EventLogWriter` 的区别，也是它必须单独存在的原因：

    - **不算 seq**。``seq`` 需要读完整个文件，既是 O(n) 又会在并发下算错；
      多个 vasp_runner 可能同时写同一份日志。这里留空，排序依据 ``ts``。
    - **单次 open-append-close**。POSIX 下追加模式写入短行是原子的，
      所以记录要保持精简（不要塞进整个 OUTCAR）。

    返回是否写成功；失败绝不能影响调用方的主流程。
    """
    try:
        path = Path(workspace).resolve() / LOG_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "v": SCHEMA_VERSION,
                "seq": None,
                "ts": _now(),
                "type": type,
                "session_id": None,
                "turn_id": None,
                "payload": encode(payload),
            },
            ensure_ascii=False,
        )
        if len(line.encode("utf-8")) > 3500:
            # 超过这个长度就不再保证追加的原子性，截断而不是冒交错的风险
            payload = {"truncated": True, "type": type, "summary": str(payload)[:1500]}
            line = json.dumps(
                {
                    "v": SCHEMA_VERSION, "seq": None, "ts": _now(), "type": type,
                    "session_id": None, "turn_id": None, "payload": payload,
                },
                ensure_ascii=False,
            )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return True
    except Exception:
        return False


def append_tool_record(
    workspace: Path | str,
    *,
    tool: str,
    ok: bool,
    duration_ms: int,
    args: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """记录一次 MCP 工具调用的结构化轨迹，追加到工作区的 ``log.jsonl``。

    SDK 只记录工具的**名字和自然语言返回**。对 VASP 场景最有价值的监督信号——
    这次挑了哪些 POTCAR、K 网格怎么来的、元素序是什么、耗时多久、成没成功——
    此前只存在于返回给模型的散文里，没有任何机器可读的记录。

    工具调用频次低（历史上 88 条轨迹共 137 次），每次开合文件的代价可以忽略，
    换来的是不必把写入器穿过整个工具闭包。失败绝不能影响工具本身的结果。
    """
    try:
        path = Path(workspace).resolve() / LOG_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "v": SCHEMA_VERSION,
            "seq": _last_seq(path) + 1,
            "ts": _now(),
            "type": "ToolInvocation",
            "session_id": None,
            "turn_id": None,
            "payload": {
                "tool": tool,
                "ok": ok,
                "duration_ms": duration_ms,
                "args": encode(args or {}),
                "detail": encode(detail or {}),
                "error": error,
            },
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        return  # 轨迹记录永远不能让工具调用本身失败


def _last_seq(path: Path) -> int:
    """续写时接着已有的 seq，避免重开会话后序号从头开始。"""
    if not path.is_file():
        return 0
    last = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = int(json.loads(line).get("seq") or last)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
    except OSError:
        return 0
    return last


# --------------------------------------------------------------------------
# 读取
# --------------------------------------------------------------------------

def read_records(path: Path | str) -> Iterator[dict[str, Any]]:
    """逐条产出记录。坏行跳过而不是中断整个文件。"""
    p = Path(path)
    if not p.is_file():
        return
    try:
        fh = p.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                yield rec


def read_messages(path: Path | str) -> Iterator[tuple[dict[str, Any], Any]]:
    """产出 ``(记录, 还原出的 SDK 对象或 None)``。UserTurn 的对象为 None。"""
    for rec in read_records(path):
        if rec.get("type") == "UserTurn":
            yield rec, None
        else:
            yield rec, decode(rec.get("payload"))


def last_session_id(path: Path | str) -> str | None:
    """取最后一次出现的 Claude session_id，供 ``--resume``。

    直接读字段，不再对整个日志跑正则。
    """
    found = None
    for rec in read_records(path):
        sid = rec.get("session_id")
        if sid:
            found = str(sid)
    return found


def resolve_log_path(workspace: Path | str) -> Path:
    """返回该工作区应读取的日志：优先 jsonl，回落到旧 log.txt。"""
    ws = Path(workspace)
    new = ws / LOG_FILENAME
    if new.is_file():
        return new
    legacy = ws / LEGACY_LOG_FILENAME
    return legacy if legacy.is_file() else new


# --------------------------------------------------------------------------
# 旧 log.txt -> log.jsonl 转换
# --------------------------------------------------------------------------

def parse_legacy_line(line: str) -> dict[str, Any] | None:
    """把旧 ``log.txt`` 的一行转成记录。用户行是 JSON，其余是 SDK ``repr``。

    ``eval`` 的命名空间是 SDK 全部 dataclass 类型；原实现只列了 8 个，导致
    ``TaskStartedMessage`` 等类型解析失败后被静默丢弃。
    """
    s = line.strip()
    if not s:
        return None
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            return None
        return {
            "v": SCHEMA_VERSION,
            "ts": None,
            "type": "UserTurn",
            "session_id": None,
            "turn_id": None,
            "payload": {"role": "user", "text": obj.get("text", "")},
        }
    try:
        obj = eval(s, {"__builtins__": {}}, SDK_TYPES)  # noqa: S307 - 受控命名空间
    except Exception:
        return None
    return {
        "v": SCHEMA_VERSION,
        "ts": None,
        "type": type(obj).__name__,
        "session_id": _extract_session_id(obj),
        "turn_id": None,
        "payload": encode(obj),
    }


def convert_legacy_log(src: Path | str, dst: Path | str) -> dict[str, int]:
    """把 ``log.txt`` 转成 ``log.jsonl``，返回统计。原文件不改动。

    ``failed`` 必须为 0 才算转换成功；调用方应据此决定是否保留结果。
    """
    src, dst = Path(src), Path(dst)
    stats = {"lines": 0, "written": 0, "failed": 0}
    out: list[str] = []
    for raw in src.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        stats["lines"] += 1
        rec = parse_legacy_line(raw)
        if rec is None:
            stats["failed"] += 1
            continue
        rec["seq"] = stats["lines"]
        try:
            out.append(json.dumps(rec, ensure_ascii=False))
        except (TypeError, ValueError):
            stats["failed"] += 1
            continue
        stats["written"] += 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
    return stats
