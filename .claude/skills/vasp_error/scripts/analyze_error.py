#!/usr/bin/env python3
import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path

STATE_FILE_NAME = ".vasp_run_state.json"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def tail_lines(path: Path, n: int = 40) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-n:]


def file_age_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


def load_check_convergence_module(repo_root: Path):
    module_path = repo_root / ".claude/skills/run_vasp/scripts/check_convergence.py"
    spec = importlib.util.spec_from_file_location("run_vasp_check_convergence", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module spec: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def detect_issue(conv: dict, state: dict | None, combined_text: str, stall_seconds: float) -> tuple[str, list[str]]:
    text = combined_text.lower()
    suggestions: list[str] = []

    if "wavecar: reading failed" in text:
        suggestions = [
            "确保续算阶段与前一阶段的 ENCUT、KSPACING 或 KPOINTS 完全一致。",
            "若参数已改变，删除旧 WAVECAR，并把 ISTART 改为 0 后重新开始该阶段。",
        ]
        return "wavecar_mismatch", suggestions

    if "zbrent" in text:
        suggestions = [
            "先确认 vasprun.xml 和 OUTCAR 是否已完整写出；若完整，通常可作为可恢复或可忽略问题处理。",
            "若仍需重跑，减小 POTIM，例如 0.1，并考虑改用 IBRION = 3 的阻尼动力学。",
            "检查初始结构是否过于激进，必要时先用更保守的松弛设置预优化。",
        ]
        return "zbrent_recoverable", suggestions

    if conv.get("reached_nelm") or "edddav" in text or "sub-space-matrix is not hermitian" in text:
        suggestions = [
            "增大 NELM，例如改到 100 或 200。",
            "把 ALGO 调整为 All 或更稳健的设置；必要时收紧/调整混合参数 AMIX、BMIX。",
            "半导体/绝缘体检查 ISMEAR 和 SIGMA；金属可适当增大 SIGMA。",
            "若是松弛计算，同时检查结构是否存在原子过近或异常对称性问题。",
        ]
        return "scf_not_converged", suggestions

    if "lapack" in text or "zpotrf failed" in text or "allocation failed" in text or "oom" in text:
        suggestions = [
            "优先怀疑内存不足：减小 K 点密度、NBANDS 或并发数。",
            "GPU/HSE 场景可重新评估 KPAR、NCORE、PRECFOCK 和 GPU 卡数配置。",
            "若是在共享节点上并发运行，减少同时提交的任务数。",
        ]
        return "memory_or_lapack_failure", suggestions

    if "fatal error" in text or "segmentation fault" in text or conv.get("fatal_error_detected"):
        suggestions = [
            "先根据日志区分是数值问题、内存问题还是输入文件问题，再决定是否重跑。",
            "若当前进程仍存活，建议先停止当前任务，再修改参数后重跑。",
        ]
        return "fatal_runtime_error", suggestions

    if "vrhfin" in text or "potcar" in text and "match" in text:
        suggestions = [
            "检查 POTCAR 中元素顺序是否与 POSCAR 第 6 行元素顺序完全一致。",
            "若顺序不一致，重新生成 POTCAR 后再提交。",
        ]
        return "potcar_order_mismatch", suggestions

    if stall_seconds > 0:
        suggestions = [
            "当前运行疑似长时间无新输出；先核实日志、OUTCAR、OSZICAR 是否确实停止更新。",
            "若确认已卡住且进程仍在，建议先用 terminate.py 定点停止，再按诊断方案重跑。",
        ]
        return "stalled_run", suggestions

    if conv.get("status") == "incomplete_postprocess":
        suggestions = [
            "电子步很可能已完成，但 vasprun.xml 不完整；优先检查 OUTCAR 和 OSZICAR 是否足以支持后处理。",
            "必要时可只重新跑后处理相关步骤，而不是立刻整轮重算。",
        ]
        return "incomplete_postprocess", suggestions

    if conv.get("status") == "unconverged":
        suggestions = [
            "当前未检测到明确收敛信号，优先检查 NELM、ALGO、ISMEAR、SIGMA 和结构质量。",
            "若是离子步问题，检查 NSW、POTIM、IBRION 和是否需要续算。",
        ]
        return "generic_unconverged", suggestions

    return "unknown", ["未匹配到明确模式，建议人工检查 OUTCAR、OSZICAR 和主日志末尾。"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze VASP failures/stalls and suggest recovery actions")
    parser.add_argument("--work-dir", type=str, default=".")
    parser.add_argument(
        "--stall-minutes",
        type=float,
        default=30.0,
        help="If the run is still marked running and no fresh output appears for this many minutes, mark as stalled",
    )
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    repo_root = Path(__file__).resolve().parents[4]
    state_path = work_dir / STATE_FILE_NAME
    state = load_json(state_path)

    check_module = load_check_convergence_module(repo_root)
    with contextlib.redirect_stdout(io.StringIO()):
        conv = check_module.check_convergence(str(work_dir))

    log_candidates: list[Path] = []
    if state and state.get("log_path"):
        log_candidates.append(Path(state["log_path"]))
    log_candidates.extend(
        [
            work_dir / "vasp.out",
            work_dir / "vasp_run.log",
            work_dir / "vasp_pbe.log",
            work_dir / "vasp_hse.log",
            work_dir / "vasp_relax.log",
            work_dir / "OUTCAR",
            work_dir / "OSZICAR",
        ]
    )

    seen: set[str] = set()
    deduped_logs: list[Path] = []
    for path in log_candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            deduped_logs.append(path)

    freshest_age = None
    freshest_path = None
    for path in deduped_logs:
        age = file_age_seconds(path)
        if age is None:
            continue
        if freshest_age is None or age < freshest_age:
            freshest_age = age
            freshest_path = path

    running_status = str((state or {}).get("status", "")).lower()
    stall_seconds = 0.0
    if running_status in {"running", "submitted", "launched"} and freshest_age is not None:
        if freshest_age >= max(0.0, args.stall_minutes) * 60.0:
            stall_seconds = freshest_age

    snippets = []
    combined_chunks = []
    for path in deduped_logs[:4]:
        lines = tail_lines(path, 30)
        snippets.append({"path": str(path), "tail": lines})
        combined_chunks.extend(lines)
    combined_text = "\n".join(combined_chunks)

    issue, suggestions = detect_issue(conv, state, combined_text, stall_seconds)
    recommend_terminate = False
    if running_status in {"running", "submitted", "launched"} and issue in {
        "fatal_runtime_error",
        "memory_or_lapack_failure",
        "wavecar_mismatch",
        "stalled_run",
    }:
        recommend_terminate = True

    result = {
        "workdir": str(work_dir),
        "state_file_found": state is not None,
        "state": state,
        "check_convergence": conv,
        "detected_issue": issue,
        "suggested_actions": suggestions,
        "freshest_output_path": str(freshest_path) if freshest_path else None,
        "freshest_output_age_seconds": freshest_age,
        "stalled_for_seconds": stall_seconds if stall_seconds > 0 else None,
        "recommend_terminate_current_run": recommend_terminate,
        "rerun_requires_termination_first": recommend_terminate,
        "evidence": snippets,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
