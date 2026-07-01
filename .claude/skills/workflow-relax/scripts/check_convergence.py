"""
检查 VASP 结构松弛的收敛状态，输出 JSON 报告。
用法: python scripts/check_convergence.py [工作目录]
默认目录: 当前目录

输出字段说明:
  ionic_converged      - 离子步是否满足 EDIFFG 收敛标准
  electronic_converged - 最后一步电子步是否收敛（复用 run_vasp 通用判据）
  nsw_reached          - 是否耗尽了最大离子步数（未收敛的征兆）
  max_force_eV_A       - 最后一离子步的最大原子力 (eV/Å)
  num_ionic_steps      - 已完成的离子步数
  contcar_exists       - CONTCAR 是否存在（松弛完成的标志）
  errors               - OUTCAR 中发现的错误行
  warnings             - OUTCAR 中发现的警告行
  last_lines           - OUTCAR 末尾 20 行（便于人工排查）
"""
from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import os
import re
import sys
from pathlib import Path


def _load_shared_checker():
    shared_path = (
        Path(__file__).resolve().parents[2] / "run_vasp" / "scripts" / "check_convergence.py"
    )
    spec = importlib.util.spec_from_file_location("run_vasp_check_convergence", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载通用收敛检查脚本: {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_convergence(work_dir="."):
    shared = _load_shared_checker()
    with contextlib.redirect_stdout(io.StringIO()):
        shared_result = shared.check_convergence(work_dir)

    result = {
        "status": shared_result["status"],
        "ionic_converged": False,
        "electronic_converged": shared_result["electronic_converged"],
        "finished_normally": shared_result["finished_normally"],
        "nsw_reached": False,
        "max_force_eV_A": None,
        "num_ionic_steps": 0,
        "contcar_exists": False,
        "errors": list(shared_result["errors"]),
        "warnings": list(shared_result["warnings"]),
        "last_lines": list(shared_result["last_lines"]),
    }

    outcar_path = os.path.join(work_dir, "OUTCAR")
    contcar_path = os.path.join(work_dir, "CONTCAR")
    result["contcar_exists"] = os.path.exists(contcar_path) and os.path.getsize(contcar_path) > 0

    if not os.path.exists(outcar_path):
        if "OUTCAR 文件不存在" not in result["errors"]:
            result["errors"].append("OUTCAR 文件不存在")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    with open(outcar_path, "r", errors="replace") as f:
        lines = f.readlines()

    nsw = None
    ionic_steps = 0
    max_force = None

    for line in lines:
        line_lower = line.lower()
        if "reached required accuracy - stopping structural energy minimisation" in line_lower:
            result["ionic_converged"] = True

        if "nsw" in line_lower and "=" in line:
            m = re.search(r"NSW\s*=\s*(\d+)", line, re.IGNORECASE)
            if m:
                nsw = int(m.group(1))

        if "- Iteration" in line:
            m = re.search(r"Iteration\s+(\d+)\s*\(", line)
            if m:
                ionic_steps = max(ionic_steps, int(m.group(1)))

        if "FORCES: max atom, RMS" in line:
            m = re.search(r"max atom, RMS\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)", line)
            if m:
                max_force = float(m.group(1))

    result["num_ionic_steps"] = ionic_steps
    result["max_force_eV_A"] = max_force
    if nsw is not None and ionic_steps >= nsw:
        result["nsw_reached"] = True

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    work_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    check_convergence(work_dir)
