"""
检查 VASP 计算的收敛状态，输出 JSON 报告。
用法: python scripts/check_convergence.py [工作目录]
默认目录: 当前目录
"""
import sys
import os
import json


def check_convergence(work_dir="."):
    result = {
        "electronic_converged": False,
        "wavecar_exists": False,
        "chgcar_exists": False,
        "wavecar_nonempty": False,
        "chgcar_nonempty": False,
        "outcar_found": False,
        "errors": [],
        "warnings": [],
        "last_lines": [],
    }

    outcar_path = os.path.join(work_dir, "OUTCAR")
    wavecar_path = os.path.join(work_dir, "WAVECAR")
    chgcar_path = os.path.join(work_dir, "CHGCAR")

    # 检查 WAVECAR / CHGCAR
    result["wavecar_exists"] = os.path.exists(wavecar_path)
    result["chgcar_exists"] = os.path.exists(chgcar_path)
    if result["wavecar_exists"]:
        result["wavecar_nonempty"] = os.path.getsize(wavecar_path) > 0
    if result["chgcar_exists"]:
        result["chgcar_nonempty"] = os.path.getsize(chgcar_path) > 0

    # 解析 OUTCAR
    if not os.path.exists(outcar_path):
        result["errors"].append("OUTCAR 文件不存在")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    result["outcar_found"] = True
    with open(outcar_path, "r", errors="replace") as f:
        lines = f.readlines()

    result["last_lines"] = [l.rstrip() for l in lines[-20:]]

    for line in lines:
        if "reached required accuracy" in line:
            result["electronic_converged"] = True
        if "WARNING" in line:
            result["warnings"].append(line.strip())
        if "ERROR" in line or "error" in line.lower():
            result["errors"].append(line.strip())

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    work_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    check_convergence(work_dir)
