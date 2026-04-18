#!/usr/bin/env python3
"""单次静态计算后检查 OUTCAR 中电子步是否达到 EDIFF 判据。

用法:
  python .../check_convergence.py [目录]
  python .../check_convergence.py .        # 当前目录下读 OUTCAR

标准输出为一行 JSON，含 ``electronic_converged`` (bool) 等字段，供 Agent / 脚本解析。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# VASP 常见「电子自洽已满足 EDIFF」提示（匹配子串，大小写敏感与 OUTCAR 一致）
_CONVERGED_MARKERS = (
    "aborting loop because EDIFF is reached",
    "reached required accuracy - stopping electronic self-consistency",
    "reached required accuracy - stopping electronic",
)

# 明确未因 EDIFF 结束电子循环时可能出现（版本差异大，仅作强否定）
_NOT_CONVERGED_MARKERS = (
    "aborting loop because EDIFF is not reached",
)


def _read_outcar(run_dir: Path) -> tuple[Path | None, str]:
    outcar = run_dir / "OUTCAR"
    if not outcar.is_file():
        return None, ""
    try:
        return outcar, outcar.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return outcar, f"__read_error__:{e}"


def analyze_outcar_text(text: str) -> tuple[bool | None, str]:
    """
    Returns:
        (True/False/None, reason). None = 无法从文本断定（例如 OUTCAR 为空或截断）。
    """
    if not text or text.startswith("__read_error__"):
        return None, "empty_or_unreadable"
    for neg in _NOT_CONVERGED_MARKERS:
        if neg in text:
            return False, f"matched:{neg!r}"
    for pos in _CONVERGED_MARKERS:
        if pos in text:
            return True, f"matched:{pos!r}"
    # 有正常结束块但无明确行时：保守为未知
    if "General timing and accounting informations" in text:
        return None, "finished_but_no_ediff_marker"
    return None, "no_convergence_marker_found"


def main() -> int:
    p = argparse.ArgumentParser(description="Check electronic SCF convergence from OUTCAR")
    p.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="包含 OUTCAR 的目录，默认当前目录",
    )
    args = p.parse_args()
    run_dir = Path(args.directory).resolve()
    outcar_path, text = _read_outcar(run_dir)

    if outcar_path is None or not text:
        out = {
            "electronic_converged": None,
            "ok": False,
            "outcar": str(run_dir / "OUTCAR"),
            "reason": "OUTCAR missing or empty",
        }
        print(json.dumps(out, ensure_ascii=False))
        return 1

    conv, detail = analyze_outcar_text(text)
    out = {
        "electronic_converged": conv,
        "ok": conv is True,
        "outcar": str(outcar_path),
        "detail": detail,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0 if conv is True else (2 if conv is False else 3)


if __name__ == "__main__":
    raise SystemExit(main())
