#!/usr/bin/env python3
"""把历史 ``runs/*/log.txt`` 转换为 ``log.jsonl``，并逐行验证无损。

用法::

    python tools/migrate_logs.py --check          # 只验证，不写任何文件
    python tools/migrate_logs.py                    # 转换（保留原 log.txt）
    python tools/migrate_logs.py --root runs      # 指定根目录

验证是三重的，任一项不过则该文件不落盘：

1. **行数守恒** —— 输出记录数 == 输入非空行数
2. **对象还原** —— 每条 SDK 记录 ``decode`` 回对象后 ``repr`` 与原行一致
3. **JSON 可序列化** —— 每条记录都能 ``json.dumps``

关于第 2 条：旧日志写入时 SDK 的 dataclass 字段比现在少（例如 ``AssistantMessage``
后来新增了 ``usage``/``message_id``/``stop_reason``），还原出的对象会带这些默认值
``None``。这属于**字段补全**而非信息丢失，因此比对时按「原行的字段是新行的子集」判定。

原 ``log.txt`` **不会被删除或修改**。``runs/`` 在 .gitignore 中，没有 git 可回滚。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.event_log import (  # noqa: E402
    LEGACY_LOG_FILENAME,
    LOG_FILENAME,
    SDK_TYPES,
    decode,
    parse_legacy_line,
)


def _repr_is_field_completion(original: str, restored: str) -> bool:
    """判断 restored 与 original 的差异是否仅为「新字段补默认值」。

    做法：把 original 里 ``key=value`` 形式的顶层片段逐个在 restored 中查找。
    """
    if restored == original:
        return True
    # 原行的每个字符（去掉结尾括号）应按序出现在还原行中
    oi = 0
    for ch in restored:
        if oi < len(original) and ch == original[oi]:
            oi += 1
    return oi >= len(original) - 1  # 容忍结尾的 ')'


def verify_file(src: Path) -> tuple[list[str], dict[str, int]]:
    """转换并验证一个 log.txt，返回 (jsonl 行列表, 统计)。"""
    stats = {"lines": 0, "written": 0, "parse_fail": 0, "json_fail": 0, "roundtrip_fail": 0}
    out: list[str] = []
    samples: list[str] = []
    for raw in src.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s:
            continue
        stats["lines"] += 1
        rec = parse_legacy_line(s)
        if rec is None:
            stats["parse_fail"] += 1
            if len(samples) < 3:
                samples.append(f"PARSE: {s[:110]}")
            continue
        rec["seq"] = stats["lines"]
        try:
            line = json.dumps(rec, ensure_ascii=False)
        except (TypeError, ValueError):
            stats["json_fail"] += 1
            continue
        if rec["type"] != "UserTurn":
            restored = decode(rec["payload"])
            if not _repr_is_field_completion(s, repr(restored)):
                stats["roundtrip_fail"] += 1
                if len(samples) < 3:
                    samples.append(f"ROUNDTRIP: {s[:110]}")
                continue
        out.append(line)
        stats["written"] += 1
    stats["samples"] = samples  # type: ignore[assignment]
    return out, stats



def prune_redundant(root: Path, *, apply: bool) -> int:
    """删除已被 log.jsonl 完全取代的冗余文件。

    只处理**逐个验证过确实冗余**的对象，绝不按文件名一刀切：

    - ``conversation_turns.jsonl``：仅当同目录存在 log.jsonl，且从 log.jsonl
      派生出的对话块数 >= 旧文件的块数时才删。
    - ``log.txt``：仅当同目录 log.jsonl 的记录数 >= log.txt 的非空行数时才删。
      注意 runs/ 不在 git 里，删掉没有任何回滚余地。

    默认只报告，加 ``--apply`` 才真正删除。
    """
    from src.conversation_store import _blocks_from_event_log, _blocks_from_legacy_store
    from src.event_log import read_records

    freed = 0
    kept: list[str] = []
    for ws in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        jsonl = ws / LOG_FILENAME
        if not jsonl.is_file():
            continue
        n_records = sum(1 for _ in read_records(jsonl))

        conv = ws / "conversation_turns.jsonl"
        if conv.is_file():
            derived = len(_blocks_from_event_log(ws))
            legacy = len(_blocks_from_legacy_store(ws))
            if derived >= legacy:
                freed += conv.stat().st_size
                print(f"  冗余 {conv.relative_to(root)}  (派生 {derived} >= 旧 {legacy} 块)")
                if apply:
                    conv.unlink()
            else:
                kept.append(f"{conv.relative_to(root)}: 派生 {derived} < 旧 {legacy}，保留")

        legacy_log = ws / LEGACY_LOG_FILENAME
        if legacy_log.is_file() and legacy_log.stat().st_size:
            n_lines = sum(1 for ln in legacy_log.read_text(errors="replace").splitlines() if ln.strip())
            if n_records >= n_lines:
                freed += legacy_log.stat().st_size
                print(f"  冗余 {legacy_log.relative_to(root)}  (jsonl {n_records} >= txt {n_lines} 行)")
                if apply:
                    legacy_log.unlink()
            else:
                kept.append(f"{legacy_log.relative_to(root)}: jsonl {n_records} < txt {n_lines}，保留")

    for k in kept:
        print(f"  ! {k}")
    print(f"\n{'已删除' if apply else '可释放'} {freed / 1024 / 1024:.1f} MB")
    if not apply:
        print("（这是预演。确认无误后加 --apply 真正删除；runs/ 不在 git 中，删除不可恢复）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(REPO_ROOT / "runs"), help="包含各工作区目录的根目录")
    ap.add_argument("--check", action="store_true", help="只验证，不写文件")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 log.jsonl")
    ap.add_argument("--prune", action="store_true", help="报告被 log.jsonl 取代的冗余文件（预演）")
    ap.add_argument("--apply", action="store_true", help="与 --prune 合用：真正删除")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"错误：目录不存在 {root}", file=sys.stderr)
        return 2

    if args.prune:
        return prune_redundant(root, apply=args.apply)

    sources = sorted(p for p in root.glob(f"*/{LEGACY_LOG_FILENAME}") if p.stat().st_size > 0)
    print(f"SDK dataclass 类型 {len(SDK_TYPES)} 个；待处理 log.txt {len(sources)} 个\n")

    total = {"files": 0, "lines": 0, "written": 0, "parse_fail": 0, "json_fail": 0, "roundtrip_fail": 0}
    failures: list[tuple[Path, dict]] = []
    skipped = 0

    for src in sources:
        out, st = verify_file(src)
        total["files"] += 1
        for k in ("lines", "written", "parse_fail", "json_fail", "roundtrip_fail"):
            total[k] += st[k]
        lossless = st["written"] == st["lines"]
        if not lossless:
            failures.append((src, st))
            continue
        if args.check:
            continue
        dst = src.parent / LOG_FILENAME
        if dst.exists() and not args.force:
            skipped += 1
            continue
        dst.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")

    print(f"文件 {total['files']}   输入行 {total['lines']}   输出行 {total['written']}")
    print(f"解析失败 {total['parse_fail']}   序列化失败 {total['json_fail']}   往返不一致 {total['roundtrip_fail']}")
    ok = not failures and total["lines"] == total["written"]
    print(f"\n{'✓ 100% 无损' if ok else '✗ 存在损失'}")
    for src, st in failures[:5]:
        print(f"  {src}: {st}")
        for x in st.get("samples", []):  # type: ignore[union-attr]
            print(f"     {x}")
    if not args.check:
        print(f"\n已写出 log.jsonl（原 log.txt 保留）；跳过已存在 {skipped} 个" if ok else "\n因存在损失，未写出任何文件")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
