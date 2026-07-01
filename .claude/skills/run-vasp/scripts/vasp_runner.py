#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

# 默认：每块将使用的 GPU 至少空闲 10 GiB（MiB 与 nvidia-smi 一致）
DEFAULT_MIN_GPU_FREE_MIB = 10240.0
# 默认：GPU 计算利用率 utilization.gpu 须严格小于该百分数（与 nvidia-smi 一致）
DEFAULT_MAX_GPU_UTIL_PERCENT = 10.0
# 空卡判定：memory.used (MiB) 不超过该值时视为「空」，优先分配；0 表示不区分空卡（仅用门控）
DEFAULT_EMPTY_GPU_MAX_USED_MIB = 512.0

STATE_SCHEMA_VERSION = 1
RUNNER_VERSION = "1.1.0"
STATE_FILE_NAME = ".vasp_run_state.json"


def utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def state_file_for_dir(work_dir: Path) -> Path:
    return work_dir / STATE_FILE_NAME


def load_state(state_path: Path) -> dict | None:
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_state(state_path: Path, data: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(state_path)


def mutate_state(state_path: Path, **updates) -> dict:
    state = load_state(state_path) or {}
    state.update(updates)
    write_state(state_path, state)
    return state


def build_task_state(
    dir_path: Path,
    task_idx: int,
    total_tasks: int,
    mode: str,
    np: int,
    exe: str,
    env_script: str,
    log_name: str,
    gpu_ids: list[int],
) -> dict:
    timestamp = int(time.time())
    run_id = f"{mode}-{timestamp}-{os.getpid()}-{task_idx}"
    resolved_env = ""
    if env_script:
        env_p = Path(env_script)
        resolved_env = str(env_p.resolve()) if env_p.exists() else env_script
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "run_id": run_id,
        "task_index": task_idx,
        "total_tasks": total_tasks,
        "mode": mode,
        "workdir": str(dir_path),
        "state_file": str(state_file_for_dir(dir_path)),
        "log_file": log_name,
        "log_path": str(dir_path / log_name),
        "exe": exe,
        "np": int(np),
        "gpu_ids": list(gpu_ids),
        "gpu_per_task": len(gpu_ids),
        "env_script": resolved_env,
        "status": "prepared",
        "created_at": utc_now_iso(),
        "started_at": None,
        "ended_at": None,
        "launch_cmd": "",
        "pid": None,
        "pgid": None,
        "returncode": None,
        "scheduler_job_id": None,
        "termination_reason": None,
        "failure_reason": None,
    }


def pid_is_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def slurm_job_is_active(job_id: str | None) -> bool:
    if not job_id:
        return False
    if shutil.which("squeue"):
        proc = subprocess.run(
            ["squeue", "-h", "-j", str(job_id), "-o", "%T"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            states = [line.strip().upper() for line in proc.stdout.splitlines() if line.strip()]
            return any(
                state not in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL"}
                for state in states
            )
    return True


def active_run_summary(state: dict) -> str:
    bits = [
        f"run_id={state.get('run_id', 'unknown')}",
        f"status={state.get('status', 'unknown')}",
    ]
    if state.get("pid"):
        bits.append(f"pid={state['pid']}")
    if state.get("pgid"):
        bits.append(f"pgid={state['pgid']}")
    if state.get("scheduler_job_id"):
        bits.append(f"job_id={state['scheduler_job_id']}")
    return ", ".join(bits)


def ensure_no_active_owned_run(dir_path: Path) -> None:
    state_path = state_file_for_dir(dir_path)
    state = load_state(state_path)
    if not state:
        return
    status = str(state.get("status", "")).lower()
    if status in {"running", "launched", "submitted"}:
        if state.get("mode") == "local" and pid_is_alive(state.get("pid")):
            raise RuntimeError(
                "existing owned local run is still active in "
                f"{dir_path}: {active_run_summary(state)}"
            )
        if state.get("mode") == "slurm" and slurm_job_is_active(state.get("scheduler_job_id")):
            raise RuntimeError(
                "existing owned scheduler run is still active in "
                f"{dir_path}: {active_run_summary(state)}"
            )


def resolve_log_file_name(
    task_idx: int,
    total_tasks: int,
    log_file: str,
    log_prefix: str,
) -> str:
    """
    统一日志命名：
    - 若显式传 --log-file，则仅允许单目录任务，直接使用该文件名；
    - 单目录默认写 `<log_prefix>.log`；
    - 多目录默认写 `<log_prefix>_<idx>.log`。
    """
    if log_file:
        if total_tasks != 1:
            raise ValueError("--log-file only supports a single task directory.")
        return log_file
    if total_tasks == 1:
        return f"{log_prefix}.log"
    return f"{log_prefix}_{task_idx}.log"


def verify_local_dependencies(exe: str, env_script: str = "") -> None:
    """本地模式执行前检查；失败时打印 ERROR 并以非零码退出，便于 Agent 从 Bash 输出识别。"""
    env_p = Path(env_script) if env_script else None
    if env_p and env_p.exists():
        check = (
            "set -e; source "
            + shlex.quote(str(env_p.resolve()))
            + "; command -v mpirun >/dev/null; command -v "
            + shlex.quote(exe)
            + " >/dev/null"
        )
        r = subprocess.run(["bash", "-c", check], capture_output=True, text=True)
        if r.returncode != 0:
            print(
                f"ERROR: After sourcing {env_script}, mpirun or {exe} not found (command not found).",
                file=sys.stderr,
            )
            sys.exit(1)
        return
    if not shutil.which("mpirun"):
        print(
            "ERROR: mpirun not found in PATH (command not found). "
            "Load your MPI module or extend PATH, e.g. via --env-script / template/env_local.sh.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not shutil.which(exe):
        print(
            f"ERROR: {exe} not found in PATH (command not found). "
            "Load your VASP module or extend PATH, e.g. via --env-script / template/env_local.sh.",
            file=sys.stderr,
        )
        sys.exit(1)


def query_gpu_free_mib() -> dict[int, float]:
    """nvidia-smi：各 GPU 索引 -> 空闲显存 (MiB)。"""
    if not shutil.which("nvidia-smi"):
        return {}
    r = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,memory.free",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return {}
    out: dict[int, float] = {}
    for line in r.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            out[int(parts[0])] = float(parts[1])
        except ValueError:
            continue
    return out


def query_gpu_utilization_percent() -> dict[int, float]:
    """nvidia-smi：各 GPU 索引 -> utilization.gpu（0–100）。"""
    if not shutil.which("nvidia-smi"):
        return {}
    r = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return {}
    out: dict[int, float] = {}
    for line in r.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            util_raw = parts[1].replace("%", "").strip()
            out[int(parts[0])] = float(util_raw)
        except ValueError:
            continue
    return out


def query_gpu_used_mib() -> dict[int, float]:
    """nvidia-smi：各 GPU 索引 -> memory.used (MiB)，用于「空卡」判定。"""
    if not shutil.which("nvidia-smi"):
        return {}
    r = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,memory.used",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return {}
    out: dict[int, float] = {}
    for line in r.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            out[int(parts[0])] = float(parts[1])
        except ValueError:
            continue
    return out


def gpu_indices_for_local_batch(num_tasks: int, gpu_per_task: int) -> list[int]:
    """本地并行时将要绑定的物理 GPU 索引。"""
    if gpu_per_task <= 0 or num_tasks <= 0:
        return []
    seen: set[int] = set()
    for i in range(num_tasks):
        start = i * gpu_per_task
        for g in range(start, start + gpu_per_task):
            seen.add(g)
    return sorted(seen)


def wait_for_min_free_gpu_memory(
    gpu_indices: list[int],
    min_free_mib: float,
    max_util_percent: float,
    poll_sec: float,
    timeout_sec: float,
) -> None:
    """
    在启动任务前等待：所列 GPU 同时满足
    - memory.free >= min_free_mib（min_free_mib <= 0 时不检查显存）
    - utilization.gpu < max_util_percent（max_util_percent <= 0 时不检查利用率）
    timeout_sec == 0 表示无限等待；>0 超时则打印 ERROR 并以码 1 退出。
    """
    if not gpu_indices:
        return
    if min_free_mib <= 0 and max_util_percent <= 0:
        return
    t0 = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        free_map = query_gpu_free_mib()
        util_map = query_gpu_utilization_percent()
        if min_free_mib > 0 and not free_map:
            print(
                "ERROR: --min-gpu-free-mib is set but nvidia-smi is missing or failed.",
                file=sys.stderr,
            )
            sys.exit(1)
        if max_util_percent > 0 and not util_map:
            print(
                "ERROR: --max-gpu-util-percent is set but nvidia-smi is missing or failed.",
                file=sys.stderr,
            )
            sys.exit(1)
        bad: list[str] = []
        for idx in gpu_indices:
            if min_free_mib > 0:
                if idx not in free_map:
                    bad.append(f"GPU {idx} not present (only {len(free_map)} device(s))")
                    continue
                f = free_map[idx]
                if f < min_free_mib:
                    bad.append(f"GPU {idx} free {f:.0f} MiB < required {min_free_mib:.0f} MiB")
            if max_util_percent > 0:
                if idx not in util_map:
                    bad.append(f"GPU {idx} has no utilization reading")
                    continue
                u = util_map[idx]
                if u >= max_util_percent:
                    bad.append(
                        f"GPU {idx} util {u:.0f}% >= limit {max_util_percent:.0f}% (need strictly less)"
                    )
        if not bad:
            parts_mem = (
                [f"GPU{i} free {free_map[i]:.0f} MiB" for i in gpu_indices]
                if min_free_mib > 0
                else []
            )
            parts_u = (
                [f"GPU{i} util {util_map[i]:.0f}%" for i in gpu_indices]
                if max_util_percent > 0
                else []
            )
            msg = "GPU gate passed: " + "; ".join([*parts_mem, *parts_u])
            print(msg, file=sys.stderr)
            return
        elapsed = time.monotonic() - t0
        if timeout_sec > 0 and elapsed >= timeout_sec:
            print(
                "ERROR: GPU gate timeout (" + str(timeout_sec) + "s): " + "; ".join(bad),
                file=sys.stderr,
            )
            sys.exit(1)
        label = "[gpu-gate]"
        print(
            f"{label} wait #{attempt} ({elapsed:.0f}s): " + "; ".join(bad),
            file=sys.stderr,
        )
        time.sleep(poll_sec)


def pick_consecutive_gpu_slot(available: set[int], k: int) -> list[int] | None:
    """
    从 available 中选 k 块**物理编号连续**的 GPU（满足 CUDA 多卡相邻假设）。
    优先使用编号最小的起点。
    """
    if k < 1 or not available:
        return None
    if k == 1:
        return [min(available)]
    sorted_avail = sorted(available)
    for i in range(len(sorted_avail) - k + 1):
        chunk = sorted_avail[i : i + k]
        if chunk == list(range(chunk[0], chunk[0] + k)):
            return chunk
    return None


def build_mpirun_shell(
    dir_path: Path,
    log_file: str,
    cuda_visible_devices: str,
    np: int,
    exe: str,
    env_script: str,
) -> str:
    env_prefix = ""
    if cuda_visible_devices:
        env_prefix = f"CUDA_VISIBLE_DEVICES={cuda_visible_devices} "
    inner = (
        f"cd {shlex.quote(str(dir_path))} && "
        f"{env_prefix}"
        f"mpirun -np {int(np)} {shlex.quote(exe)} > {shlex.quote(log_file)} 2>&1"
    )
    env_p = Path(env_script) if env_script else None
    if env_p and env_p.exists():
        inner = f"source {shlex.quote(str(env_p.resolve()))} && " + inner
    return inner


def mark_local_task_started(state_path: Path, proc: subprocess.Popen, launch_cmd: str) -> None:
    pgid = None
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = proc.pid
    mutate_state(
        state_path,
        status="running",
        started_at=utc_now_iso(),
        launch_cmd=launch_cmd,
        pid=proc.pid,
        pgid=pgid,
        failure_reason=None,
        termination_reason=None,
    )


def mark_task_finished(state_path: Path, returncode: int) -> None:
    mutate_state(
        state_path,
        status="finished" if returncode == 0 else "failed",
        ended_at=utc_now_iso(),
        returncode=int(returncode),
    )


def launch_local_task(
    task_idx: int,
    total_tasks: int,
    dir_path: Path,
    np: int,
    exe: str,
    env_script: str,
    log_name: str,
    gpu_ids: list[int],
) -> tuple[subprocess.Popen, Path, str]:
    ensure_no_active_owned_run(dir_path)
    state_path = state_file_for_dir(dir_path)
    state = build_task_state(
        dir_path=dir_path,
        task_idx=task_idx,
        total_tasks=total_tasks,
        mode="local",
        np=np,
        exe=exe,
        env_script=env_script,
        log_name=log_name,
        gpu_ids=gpu_ids,
    )
    write_state(state_path, state)
    cuda_vis = ",".join(str(g) for g in gpu_ids)
    cmd = build_mpirun_shell(dir_path, log_name, cuda_vis, np, exe, env_script)
    try:
        proc = subprocess.Popen(["bash", "-c", cmd], start_new_session=True)
    except OSError as exc:
        mutate_state(
            state_path,
            status="failed",
            ended_at=utc_now_iso(),
            failure_reason=str(exc),
            launch_cmd=cmd,
        )
        raise
    mark_local_task_started(state_path, proc, cmd)
    return proc, state_path, cmd


def gpus_tier_load_ok(
    free_map: dict[int, float],
    util_map: dict[int, float],
    min_free_mib: float,
    max_util_percent: float,
) -> set[int]:
    """
    Tier B（可上卡）：同时满足
    - memory.free >= min_free_mib（min_free_mib<=0 时不检查）
    - utilization.gpu < max_util_percent（max_util_percent<=0 时不检查）
    """
    ids = set(free_map.keys()) | set(util_map.keys())
    out: set[int] = set()
    for i in ids:
        if min_free_mib > 0:
            if i not in free_map or free_map[i] < min_free_mib:
                continue
        if max_util_percent > 0:
            if i not in util_map or util_map[i] >= max_util_percent:
                continue
        out.add(i)
    return out


def gpus_tier_empty(
    free_map: dict[int, float],
    util_map: dict[int, float],
    used_map: dict[int, float],
    min_free_mib: float,
    max_util_percent: float,
    empty_max_used_mib: float,
) -> set[int]:
    """
    Tier A（空卡优先）：在 Tier B 基础上，memory.used <= empty_max_used_mib。
    empty_max_used_mib <= 0 时返回空集，表示不启用空卡优先（仅用 Tier B）。
    """
    if empty_max_used_mib <= 0:
        return set()
    base = gpus_tier_load_ok(free_map, util_map, min_free_mib, max_util_percent)
    out: set[int] = set()
    for i in base:
        if i not in used_map:
            continue
        if used_map[i] <= empty_max_used_mib:
            out.add(i)
    return out


def pick_gpu_slot_two_tier(
    assigned: set[int],
    gpu_per_task: int,
    free_map: dict[int, float],
    util_map: dict[int, float],
    used_map: dict[int, float],
    min_free_mib: float,
    max_util_percent: float,
    empty_max_used_mib: float,
) -> tuple[list[int] | None, str]:
    """
    先在一级（空卡）里找连续槽；没有再在二级（门控可满足）里找。
    返回 (slot_or_None, reason) reason in {'empty', 'load_ok', 'none'}.
    """
    empty_set = gpus_tier_empty(
        free_map, util_map, used_map, min_free_mib, max_util_percent, empty_max_used_mib
    )
    slot = pick_consecutive_gpu_slot(empty_set - assigned, gpu_per_task)
    if slot is not None:
        return slot, "empty"
    load_ok = gpus_tier_load_ok(free_map, util_map, min_free_mib, max_util_percent)
    slot = pick_consecutive_gpu_slot(load_ok - assigned, gpu_per_task)
    if slot is not None:
        return slot, "load_ok"
    return None, "none"


def preflight_task_dirs(work_dirs: list[str]) -> None:
    for wdir in work_dirs:
        ensure_no_active_owned_run(Path(wdir).resolve())


def run_local_gpu_flexible_queue(
    work_dirs: list[str],
    np: int,
    exe: str,
    env_script: str,
    log_file: str,
    log_prefix: str,
    gpu_per_task: int,
    min_free_mib: float,
    max_util_percent: float,
    poll_sec: float,
    timeout_sec: float,
    empty_max_used_mib: float,
) -> int:
    """
    本地 flex 调度（单 vasp_runner 进程内队列）：
    1) 优先在「空卡」上起任务：满足 Tier B 门控，且 memory.used <= empty_max_used_mib；
    2) 若无空槽，在仍满足 Tier B 的卡上起（可与其它作业共享显存，只要 free/util 过线）；
    3) 若当前无可用槽，pending 在队列里轮询等待，直至有任务结束释放 assigned 或超时。
    """
    if gpu_per_task < 1:
        return 0
    preflight_task_dirs(work_dirs)
    pending: deque[tuple[int, str]] = deque(enumerate(work_dirs))
    running: list[dict] = []
    assigned: set[int] = set()
    max_rc = 0
    stall_start: float | None = None
    poll_sec = max(0.5, float(poll_sec))

    print(
        "[flex-gpu] scheduler: (1) prefer empty GPUs: tier-B gate + memory.used <= "
        f"{empty_max_used_mib if empty_max_used_mib > 0 else 'OFF'} MiB; "
        "(2) else tier-B only (memory.free >= min_free, util < max); "
        "(3) queue until a slot frees. "
        f"min_free_mib={min_free_mib}, util<{max_util_percent if max_util_percent > 0 else 'off'}%.",
        file=sys.stderr,
    )

    while pending or running:
        still: list[dict] = []
        for job in running:
            rc = job["proc"].poll()
            if rc is None:
                still.append(job)
                continue
            max_rc = max(max_rc, rc)
            for g in job["gpus"]:
                assigned.discard(g)
            mark_task_finished(job["state_path"], rc)
            print(
                f"[flex-gpu] task {job['idx']} on GPU(s) {job['gpus']} exit={rc} dir={job['wdir']}",
                file=sys.stderr,
            )
        running = still

        while pending:
            free_map = query_gpu_free_mib()
            util_map = query_gpu_utilization_percent()
            used_map = query_gpu_used_mib() if empty_max_used_mib > 0 else {}
            if min_free_mib > 0 and not free_map:
                print(
                    "ERROR: flex-gpu needs nvidia-smi to query GPU memory.",
                    file=sys.stderr,
                )
                return 1
            if max_util_percent > 0 and not util_map:
                print(
                    "ERROR: flex-gpu needs nvidia-smi to query GPU utilization.",
                    file=sys.stderr,
                )
                return 1

            slot, tier = pick_gpu_slot_two_tier(
                assigned,
                gpu_per_task,
                free_map,
                util_map,
                used_map,
                min_free_mib,
                max_util_percent,
                empty_max_used_mib,
            )
            if slot is None:
                break
            task_idx, wdir = pending.popleft()
            dir_path = Path(wdir).resolve()
            resolved_log = resolve_log_file_name(
                task_idx, len(work_dirs), log_file, log_prefix
            )
            try:
                proc, state_path, cmd = launch_local_task(
                    task_idx=task_idx,
                    total_tasks=len(work_dirs),
                    dir_path=dir_path,
                    np=np,
                    exe=exe,
                    env_script=env_script,
                    log_name=resolved_log,
                    gpu_ids=list(slot),
                )
            except (OSError, RuntimeError) as exc:
                print(f"ERROR: failed to start task {task_idx}: {exc}", file=sys.stderr)
                return 1
            for g in slot:
                assigned.add(g)
            running.append(
                {
                    "proc": proc,
                    "gpus": list(slot),
                    "idx": task_idx,
                    "wdir": str(dir_path),
                    "state_path": state_path,
                }
            )
            stall_start = None
            print(
                "[flex-gpu] start task "
                f"{task_idx} tier={tier} CUDA_VISIBLE_DEVICES={','.join(str(g) for g in slot)} "
                f"log={dir_path / resolved_log} cmd={cmd}",
                file=sys.stderr,
            )

        if not pending and not running:
            break

        if pending and not running:
            if stall_start is None:
                stall_start = time.monotonic()
            elif timeout_sec > 0 and (time.monotonic() - stall_start) >= timeout_sec:
                print(
                    "ERROR: flex-gpu timeout: no GPU satisfied gates to start next task.",
                    file=sys.stderr,
                )
                return 1
            time.sleep(poll_sec)
        else:
            stall_start = None
            time.sleep(min(2.0, poll_sec))

    print("[flex-gpu] all tasks finished.", file=sys.stderr)
    return max_rc


def run_local_fixed_batch(
    work_dirs: list[str],
    np: int,
    exe: str,
    env_script: str,
    gpu_per_task: int,
    log_file: str,
    log_prefix: str,
) -> int:
    preflight_task_dirs(work_dirs)
    running: list[dict] = []
    max_rc = 0
    launch_failed = False

    for task_idx, wdir in enumerate(work_dirs):
        dir_path = Path(wdir).resolve()
        resolved_log = resolve_log_file_name(task_idx, len(work_dirs), log_file, log_prefix)
        gpu_ids: list[int] = []
        if gpu_per_task > 0:
            gpu_start = task_idx * gpu_per_task
            gpu_ids = list(range(gpu_start, gpu_start + gpu_per_task))
        try:
            proc, state_path, cmd = launch_local_task(
                task_idx=task_idx,
                total_tasks=len(work_dirs),
                dir_path=dir_path,
                np=np,
                exe=exe,
                env_script=env_script,
                log_name=resolved_log,
                gpu_ids=gpu_ids,
            )
        except (OSError, RuntimeError) as exc:
            print(f"ERROR: failed to start task {task_idx}: {exc}", file=sys.stderr)
            launch_failed = True
            max_rc = max(max_rc, 1)
            continue
        running.append(
            {
                "proc": proc,
                "idx": task_idx,
                "wdir": str(dir_path),
                "state_path": state_path,
            }
        )
        print(
            f"[local-run] task={task_idx} dir={dir_path} log={dir_path / resolved_log} cmd={cmd}",
            file=sys.stderr,
        )

    while running:
        still: list[dict] = []
        for job in running:
            rc = job["proc"].poll()
            if rc is None:
                still.append(job)
                continue
            mark_task_finished(job["state_path"], rc)
            max_rc = max(max_rc, rc)
            print(
                f"[local-run] task {job['idx']} exit={rc} dir={job['wdir']}",
                file=sys.stderr,
            )
        running = still
        if running:
            time.sleep(1.0)

    if launch_failed:
        print("ERROR: one or more local tasks failed to launch.", file=sys.stderr)
    print("All local VASP tasks completed.", file=sys.stderr)
    return max_rc


def create_slurm_script(work_dirs, np, exe, env_script, template_path, log_file, log_prefix):
    """场景2：基于模板生成 Slurm 脚本并提交"""
    if not Path(template_path).exists():
        raise FileNotFoundError(f"Slurm template not found at {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    template = template.replace("{{NTASKS}}", str(np))

    run_commands = []
    if env_script and Path(env_script).exists():
        run_commands.append(f"source {env_script}")

    for i, wdir in enumerate(work_dirs):
        dir_path = Path(wdir).resolve()
        resolved_log = resolve_log_file_name(i, len(work_dirs), log_file, log_prefix)
        run_commands.append(f"cd {dir_path}")
        run_commands.append(f"echo '[slurm-run] dir={dir_path} log={dir_path / resolved_log}'")
        run_commands.append(f"mpirun -np {np} {exe} > {resolved_log} 2>&1")
        run_commands.append("cd - > /dev/null")

    template = template.replace("{{COMMANDS}}", "\n".join(run_commands))
    return template


def parse_sbatch_job_id(stdout: str) -> str | None:
    for token in stdout.replace("\n", " ").split():
        if token.isdigit():
            return token
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VASP Task Orchestrator")
    parser.add_argument("--dirs", nargs="+", required=True, help="List of task directories")
    parser.add_argument("--mode", choices=["local", "slurm"], required=True)
    parser.add_argument("--np", type=int, default=4, help="MPI tasks PER directory")
    parser.add_argument("--exe", type=str, default="vasp_std")
    parser.add_argument("--gpu-per-task", type=int, default=0, help="GPUs to bind per task")
    parser.add_argument("--env-script", type=str, default="")
    parser.add_argument("--slurm-template", type=str, default="")
    parser.add_argument(
        "--log-file",
        type=str,
        default="",
        help="单目录任务时的日志文件名；例如 vasp_pbe.log 或 vasp_hse.log",
    )
    parser.add_argument(
        "--log-prefix",
        type=str,
        default="vasp_run",
        help="默认日志前缀；单目录写 <prefix>.log，多目录写 <prefix>_<idx>.log",
    )
    parser.add_argument(
        "--min-gpu-free-mib",
        type=float,
        default=DEFAULT_MIN_GPU_FREE_MIB,
        help=(
            "本地且 --gpu-per-task>0 时：所分配 GPU 的 memory.free (MiB) 均需 ≥ 该值后再启动；"
            f"默认 {DEFAULT_MIN_GPU_FREE_MIB:.0f}（约 10GiB/卡）。传 0 可关闭检查"
        ),
    )
    parser.add_argument(
        "--max-gpu-util-percent",
        type=float,
        default=DEFAULT_MAX_GPU_UTIL_PERCENT,
        help=(
            "本地且 --gpu-per-task>0：所分配 GPU 的 utilization.gpu (%%) 须 **严格小于** 该值后再启动；"
            f"默认 {DEFAULT_MAX_GPU_UTIL_PERCENT:.0f}。传 0 可关闭利用率检查"
        ),
    )
    parser.add_argument(
        "--gpu-ready-poll-sec",
        type=float,
        default=10.0,
        help="等待空闲显存时的轮询间隔（秒）",
    )
    parser.add_argument(
        "--gpu-ready-timeout-sec",
        type=float,
        default=0.0,
        help="等待空闲显存的最长时间（秒）；0=不超时、一直等",
    )
    parser.add_argument(
        "--fixed-gpu-layout",
        action="store_true",
        help=(
            "本地+GPU 时：使用旧逻辑（任务 i 固定绑 GPU i, i+1, …），"
            "启动前要求所涉 GPU 同时满足 min_free_mib；默认关闭，使用灵活队列调度"
        ),
    )
    parser.add_argument(
        "--empty-gpu-max-used-mib",
        type=float,
        default=DEFAULT_EMPTY_GPU_MAX_USED_MIB,
        help=(
            "flex 调度优先「空卡」：memory.used (MiB) 需 <= 该值且满足 min_free/util 才算空卡。"
            f" 默认 {DEFAULT_EMPTY_GPU_MAX_USED_MIB:.0f}；传 0 关闭空卡优先（仅用 min_free+util 选卡）"
        ),
    )
    args = parser.parse_args()

    if args.log_file and len(args.dirs) != 1:
        print(
            "ERROR: --log-file only supports a single task directory. "
            "Use --log-prefix for multi-directory runs.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.mode == "local":
        verify_local_dependencies(args.exe, args.env_script)
        if args.gpu_per_task > 0 and not args.fixed_gpu_layout:
            rc = run_local_gpu_flexible_queue(
                args.dirs,
                args.np,
                args.exe,
                args.env_script,
                args.log_file,
                args.log_prefix,
                args.gpu_per_task,
                args.min_gpu_free_mib,
                args.max_gpu_util_percent,
                max(1.0, args.gpu_ready_poll_sec),
                max(0.0, args.gpu_ready_timeout_sec),
                args.empty_gpu_max_used_mib,
            )
            if rc != 0:
                print(
                    f"ERROR: flex-gpu local run failed (exit code {rc}). "
                    "Check vasp_run_*.log in each task directory.",
                    file=sys.stderr,
                )
                sys.exit(rc)
        else:
            if args.gpu_per_task > 0 and args.fixed_gpu_layout and (
                args.min_gpu_free_mib > 0 or args.max_gpu_util_percent > 0
            ):
                indices = gpu_indices_for_local_batch(len(args.dirs), args.gpu_per_task)
                wait_for_min_free_gpu_memory(
                    indices,
                    args.min_gpu_free_mib,
                    args.max_gpu_util_percent,
                    max(1.0, args.gpu_ready_poll_sec),
                    max(0.0, args.gpu_ready_timeout_sec),
                )
            rc = run_local_fixed_batch(
                args.dirs,
                args.np,
                args.exe,
                args.env_script,
                args.gpu_per_task,
                args.log_file,
                args.log_prefix,
            )
            if rc != 0:
                print(
                    f"ERROR: local orchestration exited with code {rc}. "
                    "Check task state files and vasp logs in each task directory.",
                    file=sys.stderr,
                )
                sys.exit(rc)

    elif args.mode == "slurm":
        preflight_task_dirs(args.dirs)
        content = create_slurm_script(
            args.dirs,
            args.np,
            args.exe,
            args.env_script,
            args.slurm_template,
            args.log_file,
            args.log_prefix,
        )
        submit_script = Path("submit_vasp.slurm")
        submit_script.write_text(content, encoding="utf-8")
        print(f"Generated Slurm submission script: {submit_script}")
        print("Submitting to cluster...")
        proc = subprocess.run(
            ["sbatch", submit_script.name],
            capture_output=True,
            text=True,
        )
        if proc.stdout:
            print(proc.stdout.strip())
        if proc.stderr:
            print(proc.stderr.strip(), file=sys.stderr)
        if proc.returncode != 0:
            print(f"ERROR: sbatch failed with code {proc.returncode}", file=sys.stderr)
            sys.exit(proc.returncode)
        job_id = parse_sbatch_job_id(proc.stdout)
        for task_idx, wdir in enumerate(args.dirs):
            dir_path = Path(wdir).resolve()
            resolved_log = resolve_log_file_name(task_idx, len(args.dirs), args.log_file, args.log_prefix)
            state = build_task_state(
                dir_path=dir_path,
                task_idx=task_idx,
                total_tasks=len(args.dirs),
                mode="slurm",
                np=args.np,
                exe=args.exe,
                env_script=args.env_script,
                log_name=resolved_log,
                gpu_ids=[],
            )
            state.update(
                {
                    "status": "submitted",
                    "started_at": utc_now_iso(),
                    "launch_cmd": f"sbatch {submit_script.name}",
                    "scheduler_job_id": job_id,
                }
            )
            write_state(state_file_for_dir(dir_path), state)
