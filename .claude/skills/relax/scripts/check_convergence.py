"""
检查 VASP 结构松弛的收敛状态，输出 JSON 报告。
用法: python scripts/check_convergence.py [工作目录]
默认目录: 当前目录

输出字段说明:
  ionic_converged     - 离子步是否满足 EDIFFG 收敛标准
  electronic_converged- 最后一步电子步是否收敛
  nsw_reached         - 是否耗尽了最大离子步数（未收敛的征兆）
  max_force_eV_A      - 最后一离子步的最大原子力 (eV/Å)
  num_ionic_steps     - 已完成的离子步数
  contcar_exists      - CONTCAR 是否存在（松弛完成的标志）
  errors              - OUTCAR 中发现的 ERROR 行
  warnings            - OUTCAR 中发现的 WARNING 行
  last_lines          - OUTCAR 末尾 20 行（便于人工排查）
"""
import sys
import os
import re
import json


def check_convergence(work_dir="."):
    result = {
        "ionic_converged": False,
        "electronic_converged": False,
        "nsw_reached": False,
        "max_force_eV_A": None,
        "num_ionic_steps": 0,
        "contcar_exists": False,
        "errors": [],
        "warnings": [],
        "last_lines": [],
    }

    outcar_path = os.path.join(work_dir, "OUTCAR")
    contcar_path = os.path.join(work_dir, "CONTCAR")

    result["contcar_exists"] = os.path.exists(contcar_path) and os.path.getsize(contcar_path) > 0

    if not os.path.exists(outcar_path):
        result["errors"].append("OUTCAR 文件不存在")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    with open(outcar_path, "r", errors="replace") as f:
        lines = f.readlines()

    result["last_lines"] = [l.rstrip() for l in lines[-20:]]

    nsw = None
    ionic_steps = 0
    max_force = None

    for line in lines:
        # 电子步收敛
        if "reached required accuracy" in line:
            result["electronic_converged"] = True

        # 离子步收敛（EDIFFG 力收敛判据）
        if "reached required accuracy - stopping structural energy minimisation" in line:
            result["ionic_converged"] = True

        # 读取 NSW 设置
        if "NSW" in line and "=" in line:
            m = re.search(r"NSW\s*=\s*(\d+)", line)
            if m:
                nsw = int(m.group(1))

        # 统计离子步数
        if "- Iteration" in line:
            m = re.search(r"Iteration\s+(\d+)\s*\(", line)
            if m:
                ionic_steps = max(ionic_steps, int(m.group(1)))

        # 提取最大力（最后一次出现）
        if "FORCES: max atom, RMS" in line:
            m = re.search(r"max atom, RMS\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)", line)
            if m:
                max_force = float(m.group(1))

        if "WARNING" in line:
            result["warnings"].append(line.strip())
        if line.strip().startswith("ERROR") or "fatal error" in line.lower():
            result["errors"].append(line.strip())

    result["num_ionic_steps"] = ionic_steps
    result["max_force_eV_A"] = max_force
    if nsw is not None and ionic_steps >= nsw:
        result["nsw_reached"] = True

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    work_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    check_convergence(work_dir)
