#!/usr/bin/env python3
"""把一次会话的完整日志压缩成可直接喂给模型的轨迹摘要。

原始 ``log.jsonl`` 动辄几百 KB（实测单个工作区 428 KB），其中大量体积来自
每次 Skill 调用重复注入的 SKILL.md 全文和冗长的工具返回。直接 Read 会吃掉大量
上下文且信噪比极低。本脚本抽取蒸馏真正需要的信号，实测压缩到原体积的 5–10%。

用法::

    python extract_trajectory.py <工作区目录或日志文件>
    python extract_trajectory.py runs/bg_Ga2O3 --errors-only
    python extract_trajectory.py runs/bg_Ga2O3 --format json -o traj.json

输出（默认 markdown）包含：

- 会话概览：轮次、耗时、成本、token、使用过的 skill
- 事件流：用户输入 / 助手要点 / 工具调用（参数摘要）/ 工具结果（失败保留更多正文）
- 失败清单：所有 ``is_error`` 的工具返回及其对应调用——这是改进 skill 的主要依据
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.event_log import read_messages, resolve_log_path  # noqa: E402

SKILL_MARKER = "Base directory for this skill:"
TOOL_INPUT_LIMIT = 400
RESULT_OK_LIMIT = 120
RESULT_ERR_LIMIT = 600
TEXT_LIMIT = 400


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f" …[截断，共 {len(text)} 字符]"


def _blocks(msg: Any) -> list[Any]:
    content = getattr(msg, "content", None)
    return content if isinstance(content, list) else []


def extract(log_path: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    pending: dict[str, str] = {}      # tool_use_id -> 工具名
    skills_used: list[str] = []
    totals = {"turns": 0, "duration_ms": 0, "cost_usd": 0.0,
              "input_tokens": 0, "output_tokens": 0, "errors": 0}
    skill_body_bytes = 0

    for rec, msg in read_messages(log_path):
        rtype = rec.get("type")
        ts = rec.get("ts")

        if rtype == "UserTurn":
            events.append({"kind": "user", "ts": ts,
                           "text": _clip((rec.get("payload") or {}).get("text", ""), TEXT_LIMIT)})
            continue
        if msg is None:
            continue

        if rtype == "AssistantMessage":
            for b in _blocks(msg):
                bt = type(b).__name__
                if bt == "TextBlock":
                    t = _clip(getattr(b, "text", ""), TEXT_LIMIT)
                    if t:
                        events.append({"kind": "say", "ts": ts, "text": t})
                elif bt in ("ToolUseBlock", "ServerToolUseBlock"):
                    name = getattr(b, "name", "?")
                    pending[getattr(b, "id", "")] = name
                    try:
                        raw = json.dumps(getattr(b, "input", {}), ensure_ascii=False)
                    except (TypeError, ValueError):
                        raw = str(getattr(b, "input", ""))
                    if name == "Skill":
                        sk = (getattr(b, "input", {}) or {}).get("skill") or "?"
                        if sk not in skills_used:
                            skills_used.append(str(sk))
                    events.append({"kind": "tool", "ts": ts, "name": name,
                                   "input": _clip(raw, TOOL_INPUT_LIMIT)})
            continue

        if rtype == "UserMessage":
            for b in _blocks(msg):
                bt = type(b).__name__
                if bt in ("ToolResultBlock", "ServerToolResultBlock"):
                    is_err = bool(getattr(b, "is_error", False))
                    body = str(getattr(b, "content", ""))
                    if is_err:
                        totals["errors"] += 1
                    events.append({
                        "kind": "result", "ts": ts,
                        "tool": pending.get(getattr(b, "tool_use_id", ""), "?"),
                        "error": is_err,
                        "output": _clip(body, RESULT_ERR_LIMIT if is_err else RESULT_OK_LIMIT),
                    })
                elif bt == "TextBlock":
                    text = getattr(b, "text", "") or ""
                    # SKILL.md 全文注入：只记一行引用，正文不进摘要
                    if text.lstrip().startswith(SKILL_MARKER):
                        skill_body_bytes += len(text)
                        events.append({"kind": "skill_loaded", "ts": ts,
                                       "ref": text.splitlines()[0][:120]})
                    else:
                        events.append({"kind": "context", "ts": ts, "text": _clip(text, TEXT_LIMIT)})
            continue

        if rtype == "ResultMessage":
            totals["turns"] += 1
            totals["duration_ms"] += getattr(msg, "duration_ms", 0) or 0
            totals["cost_usd"] += getattr(msg, "total_cost_usd", 0) or 0
            usage = getattr(msg, "usage", None) or {}
            if isinstance(usage, dict):
                totals["input_tokens"] += usage.get("input_tokens") or 0
                totals["output_tokens"] += usage.get("output_tokens") or 0
            events.append({"kind": "turn_end", "ts": ts,
                           "error": bool(getattr(msg, "is_error", False)),
                           "stop_reason": getattr(msg, "stop_reason", None),
                           "seconds": round((getattr(msg, "duration_ms", 0) or 0) / 1000)})
            continue

        if rtype == "VaspRunEvent":
            d = rec.get("payload") or {}
            bits = [f"{d.get('event')} {d.get('dir')}"]
            if d.get("exe"):
                bits.append(f"{d['exe']} np={d.get('np')} gpu={d.get('gpu_ids')}")
            if d.get("returncode") is not None:
                bits.append(f"rc={d['returncode']}")
            if d.get("failure_reason"):
                bits.append(f"失败: {d['failure_reason']}")
            events.append({"kind": "vasp", "ts": ts, "text": " | ".join(str(b) for b in bits)})
            if d.get("event") == "finished" and d.get("returncode") not in (0, None):
                totals["errors"] += 1
            continue

        if rtype in ("TaskStartedMessage", "TaskNotificationMessage", "TaskUpdatedMessage"):
            data = getattr(msg, "data", None) or {}
            note = data.get("summary") or data.get("description") or data.get("status") or ""
            if note:
                events.append({"kind": "background", "ts": ts, "text": _clip(str(note), 200)})

    return {"log": str(log_path), "totals": totals, "skills_used": skills_used,
            "skill_body_bytes": skill_body_bytes, "events": events}


def to_markdown(data: dict[str, Any], errors_only: bool = False) -> str:
    t = data["totals"]
    out = [f"# 执行轨迹摘要 — {Path(data['log']).parent.name}", ""]
    out.append(f"- 日志：`{data['log']}`")
    out.append(f"- 轮次 {t['turns']}，累计 {t['duration_ms']/1000:.0f} s，"
               f"成本 ${t['cost_usd']:.4f}，token {t['input_tokens']}/{t['output_tokens']}")
    out.append(f"- 工具失败 **{t['errors']}** 次")
    out.append(f"- 使用过的 skill：{', '.join(data['skills_used']) or '（无）'}")
    if data["skill_body_bytes"]:
        out.append(f"- 已折叠的 SKILL 正文注入：{data['skill_body_bytes']/1024:.0f} KB")
    out.append("")

    failures = [e for e in data["events"] if e["kind"] == "result" and e["error"]]
    if failures:
        out += ["## 失败清单（改进 skill 的主要依据）", ""]
        for i, e in enumerate(failures, 1):
            out.append(f"{i}. **{e['tool']}** — {e['output']}")
        out.append("")
    if errors_only:
        return "\n".join(out)

    out += ["## 事件流", ""]
    for e in data["events"]:
        k = e["kind"]
        if k == "user":
            out.append(f"- 👤 **用户**：{e['text']}")
        elif k == "say":
            out.append(f"- 💬 {e['text']}")
        elif k == "tool":
            out.append(f"- 🛠 `{e['name']}` ← {e['input']}")
        elif k == "result":
            out.append(f"  - {'❌' if e['error'] else '✅'} {e['tool']}: {e['output']}")
        elif k == "skill_loaded":
            out.append(f"- 📘 加载 skill：{e['ref']}")
        elif k == "vasp":
            out.append(f"- ⚛️ VASP：{e['text']}")
        elif k == "background":
            out.append(f"- ⏳ 后台：{e['text']}")
        elif k == "context":
            out.append(f"- 📄 上下文：{e['text']}")
        elif k == "turn_end":
            out.append(f"- ── 本轮结束（{'失败' if e['error'] else '成功'}，{e['seconds']} s）")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="工作区目录，或直接给 log.jsonl / log.txt 路径")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--errors-only", action="store_true", help="只输出概览与失败清单")
    ap.add_argument("-o", "--output", help="写入文件；缺省打印到标准输出")
    args = ap.parse_args()

    target = Path(args.target)
    log_path = target if target.is_file() else resolve_log_path(target)
    if not log_path.is_file():
        print(f"错误：找不到日志 {log_path}", file=sys.stderr)
        return 2

    data = extract(log_path)
    text = json.dumps(data, ensure_ascii=False, indent=2) if args.format == "json" \
        else to_markdown(data, errors_only=args.errors_only)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        raw = log_path.stat().st_size
        print(f"已写出 {args.output}（原始 {raw/1024:.0f} KB → 摘要 "
              f"{len(text.encode())/1024:.0f} KB，{100*len(text.encode())/max(raw,1):.1f}%）")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
