"""
检查 VASP 计算的收敛状态，输出 JSON 报告。
用法: python scripts/check_convergence.py [工作目录]
默认目录: 当前目录
"""
import sys
import os
import json


CONVERGENCE_MARKERS = (
    "reached required accuracy",
    "aborting loop because ediff is reached",
)

NONFATAL_ERROR_MARKERS = (
    "kinetic energy error for atom=",
)

FATAL_ERROR_MARKERS = (
    "fatal error",
    "segmentation fault",
    "internal error",
)

KNOWN_RECOVERABLE_FATAL_MARKERS = (
    "zbrent: fatal error",
)


def _scan_oszicar(oszicar_path):
    """从 OSZICAR 末尾提取收敛线索。"""
    info = {
        "exists": False,
        "final_energy_line_found": False,
        "last_iteration_index": None,
        "last_lines": [],
    }
    if not os.path.exists(oszicar_path):
        return info

    info["exists"] = True
    with open(oszicar_path, "r", errors="replace") as f:
        lines = [line.rstrip() for line in f.readlines()]

    info["last_lines"] = lines[-20:]
    info["final_energy_line_found"] = any(
        (" F=" in line and " E0=" in line) for line in lines[-10:]
    )
    for line in reversed(lines):
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("DAV:", "RMM:", "CG:", "DMP:", "SDA:"):
            try:
                info["last_iteration_index"] = int(parts[1])
            except ValueError:
                pass
            break
    return info


def _scan_vasprun(vasprun_path):
    """轻量检查 vasprun.xml 是否存在且至少像一个完整 XML。"""
    info = {
        "exists": False,
        "nonempty": False,
        "appears_complete": False,
    }
    if not os.path.exists(vasprun_path):
        return info

    info["exists"] = True
    info["nonempty"] = os.path.getsize(vasprun_path) > 0
    if not info["nonempty"]:
        return info

    with open(vasprun_path, "rb") as f:
        try:
            f.seek(max(0, os.path.getsize(vasprun_path) - 4096))
            tail = f.read().decode("utf-8", errors="replace").lower()
        except OSError:
            tail = ""

    info["appears_complete"] = "</modeling>" in tail
    return info


def _derive_status(result):
    """
    汇总判定优先级：
    1. failed: 明确 fatal error
    2. unconverged: 达到 NELM 或未检测到电子收敛
    3. incomplete_postprocess: 计算完成但 vasprun.xml 不完整
    4. converged: 收敛且后处理文件完整
    5. running_or_incomplete: 其余中间态
    """
    if result["fatal_error_detected"]:
        return "failed"
    if result["reached_nelm"] or not result["electronic_converged"]:
        return "unconverged"
    if result["finished_normally"] and not result["vasprun_complete"]:
        return "incomplete_postprocess"
    if result["electronic_converged"] and (
        result["vasprun_complete"] or result["ionic_step_finished"]
    ):
        return "converged"
    return "running_or_incomplete"


def check_convergence(work_dir="."):
    result = {
        "status": "running_or_incomplete",
        "electronic_converged": False,
        "finished_normally": False,
        "ionic_step_finished": False,
        "reached_nelm": False,
        "fatal_error_detected": False,
        "wavecar_exists": False,
        "chgcar_exists": False,
        "wavecar_nonempty": False,
        "chgcar_nonempty": False,
        "outcar_found": False,
        "oszicar_found": False,
        "vasprun_found": False,
        "vasprun_nonempty": False,
        "vasprun_complete": False,
        "errors": [],
        "warnings": [],
        "last_lines": [],
    }

    outcar_path = os.path.join(work_dir, "OUTCAR")
    oszicar_path = os.path.join(work_dir, "OSZICAR")
    vasprun_path = os.path.join(work_dir, "vasprun.xml")
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
    outcar_lower = [line.lower() for line in lines]
    finished_normally = any(
        "general timing and accounting informations for this job" in line
        for line in outcar_lower[-100:]
    )
    result["finished_normally"] = finished_normally
    result["ionic_step_finished"] = any(
        (" free  energy   toten" in line) or ("free energy of the ion-electron system" in line)
        for line in outcar_lower[-200:]
    )

    nelm_limit = None

    for line in lines:
        line_lower = line.lower()
        if "nelm" in line_lower and "maximum electronic steps" not in line_lower:
            parts = line.replace("=", " ").split()
            for idx, token in enumerate(parts):
                if token.upper() == "NELM" and idx + 1 < len(parts):
                    try:
                        nelm_limit = int(float(parts[idx + 1].rstrip(";,")))
                    except ValueError:
                        pass
        if any(marker in line_lower for marker in CONVERGENCE_MARKERS):
            result["electronic_converged"] = True
        if "WARNING" in line:
            result["warnings"].append(line.strip())
        if any(marker in line_lower for marker in FATAL_ERROR_MARKERS):
            if any(marker in line_lower for marker in KNOWN_RECOVERABLE_FATAL_MARKERS):
                result["warnings"].append(line.strip())
                continue
            result["fatal_error_detected"] = True
            result["errors"].append(line.strip())
            continue
        if "ERROR" in line or "error" in line_lower:
            if any(marker in line_lower for marker in NONFATAL_ERROR_MARKERS):
                result["warnings"].append(line.strip())
                continue
            result["errors"].append(line.strip())

    oszicar_info = _scan_oszicar(oszicar_path)
    result["oszicar_found"] = oszicar_info["exists"]
    if nelm_limit is not None and oszicar_info["last_iteration_index"] is not None:
        result["reached_nelm"] = oszicar_info["last_iteration_index"] >= nelm_limit

    vasprun_info = _scan_vasprun(vasprun_path)
    result["vasprun_found"] = vasprun_info["exists"]
    result["vasprun_nonempty"] = vasprun_info["nonempty"]
    result["vasprun_complete"] = vasprun_info["appears_complete"]

    # 某些 VASP 版本不会打印 "reached required accuracy"，但会正常写出 OSZICAR 终行
    # 和 OUTCAR 收尾统计信息；这类情况同样视为电子步正常结束。
    if (
        not result["electronic_converged"]
        and finished_normally
        and oszicar_info["final_energy_line_found"]
    ):
        result["electronic_converged"] = True

    # 已触发明确 fatal error 时，无论局部文件是否写出，都不判定为电子收敛。
    if result["fatal_error_detected"]:
        result["electronic_converged"] = False

    # 若打满 NELM 且没有任何收敛信号，则视为未收敛。
    if result["reached_nelm"] and not any(
        marker in line for line in outcar_lower for marker in CONVERGENCE_MARKERS
    ):
        result["electronic_converged"] = False
        if not any("nelm" in err.lower() for err in result["errors"]):
            result["errors"].append("可能达到 NELM 上限但未检测到电子收敛标志")

    # vasprun.xml 缺失不应覆盖已经由 OUTCAR/OSZICAR 确认的收敛，只作为后处理风险提示。
    if finished_normally and not result["vasprun_complete"]:
        result["warnings"].append("vasprun.xml 缺失、为空或末尾不完整；后处理可能失败")

    result["status"] = _derive_status(result)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    work_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    check_convergence(work_dir)
