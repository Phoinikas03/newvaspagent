#!/usr/bin/env python3
import os
import sys
import time
import argparse
import subprocess
import shlex
import shutil
from collections import deque
from pathlib import Path

# 默认：每块将使用的 GPU 至少空闲 10 GiB（MiB 与 nvidia-smi 一致）
DEFAULT_MIN_GPU_FREE_MIB = 10240.0


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


def gpu_indices_for_local_batch(num_tasks: int, gpu_per_task: int) -> list[int]:
    """本地并行时将要绑定的物理 GPU 索引（与 create_local_batch_script 中逻辑一致）。"""
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
    poll_sec: float,
    timeout_sec: float,
) -> None:
    """
    在启动任务前等待：所列 GPU 的 memory.free 均 >= min_free_mib。
    min_free_mib <= 0 时不检查。
    timeout_sec == 0 表示无限等待；>0 超时则打印 ERROR 并以码 1 退出。
    """
    if min_free_mib <= 0 or not gpu_indices:
        return
    t0 = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        free_map = query_gpu_free_mib()
        if not free_map:
            print(
                "ERROR: --min-gpu-free-mib is set but nvidia-smi is missing or failed.",
                file=sys.stderr,
            )
            sys.exit(1)
        bad: list[str] = []
        for idx in gpu_indices:
            if idx not in free_map:
                bad.append(f"GPU {idx} not present (only {len(free_map)} device(s))")
                continue
            f = free_map[idx]
            if f < min_free_mib:
                bad.append(f"GPU {idx} free {f:.0f} MiB < required {min_free_mib:.0f} MiB")
        if not bad:
            parts = [f"GPU{i} free {free_map[i]:.0f} MiB" for i in gpu_indices]
            print("GPU memory gate passed: " + "; ".join(parts), file=sys.stderr)
            return
        elapsed = time.monotonic() - t0
        if timeout_sec > 0 and elapsed >= timeout_sec:
            print(
                "ERROR: GPU memory gate timeout (" + str(timeout_sec) + "s): " + "; ".join(bad),
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            f"[min-gpu-free-mib] wait #{attempt} ({elapsed:.0f}s): " + "; ".join(bad),
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
    inner = (
        f"cd {shlex.quote(str(dir_path))} && "
        f"CUDA_VISIBLE_DEVICES={cuda_visible_devices} "
        f"mpirun -np {int(np)} {shlex.quote(exe)} > {shlex.quote(log_file)} 2>&1"
    )
    env_p = Path(env_script) if env_script else None
    if env_p and env_p.exists():
        inner = f"source {shlex.quote(str(env_p.resolve()))} && " + inner
    return inner


def run_local_gpu_flexible_queue(
    work_dirs: list[str],
    np: int,
    exe: str,
    env_script: str,
    gpu_per_task: int,
    min_free_mib: float,
    poll_sec: float,
    timeout_sec: float,
) -> int:
    """
    动态挑选当前满足空闲显存的 GPU；任务数多于可同时占用的卡时在进程内排队。
    返回 0 表示全部子进程退出码为 0，否则为最大非零退出码（无子进程失败时为 0）。
    """
    if gpu_per_task < 1:
        return 0
    pending: deque[tuple[int, str]] = deque(enumerate(work_dirs))
    running: list[dict] = []
    assigned: set[int] = set()
    max_rc = 0
    stall_start: float | None = None
    poll_sec = max(0.5, float(poll_sec))

    print(
        "[flex-gpu] scheduler: assign free GPUs by nvidia-smi memory.free; "
        f"queue when tasks > available slots (min_free_mib={min_free_mib}).",
        file=sys.stderr,
    )

    while pending or running:
        # 回收已结束任务
        still: list[dict] = []
        for job in running:
            rc = job["proc"].poll()
            if rc is None:
                still.append(job)
                continue
            max_rc = max(max_rc, rc)
            for g in job["gpus"]:
                assigned.discard(g)
            print(
                f"[flex-gpu] task {job['idx']} on GPU(s) {job['gpus']} exit={rc} dir={job['wdir']}",
                file=sys.stderr,
            )
        running = still

        # 尽量从队列中启动新任务
        while pending:
            free_map = query_gpu_free_mib()
            if not free_map:
                print(
                    "ERROR: flex-gpu needs nvidia-smi to query GPU memory.",
                    file=sys.stderr,
                )
                return 1
            if min_free_mib > 0:
                eligible = {i for i, f in free_map.items() if f >= min_free_mib}
            else:
                eligible = set(free_map.keys())
            available = eligible - assigned
            slot = pick_consecutive_gpu_slot(available, gpu_per_task)
            if slot is None:
                break
            task_idx, wdir = pending.popleft()
            dir_path = Path(wdir).resolve()
            log_file = f"vasp_run_{task_idx}.log"
            cuda_vis = ",".join(str(g) for g in slot)
            cmd = build_mpirun_shell(
                dir_path, log_file, cuda_vis, np, exe, env_script
            )
            try:
                proc = subprocess.Popen(["bash", "-c", cmd])
            except OSError as e:
                print(f"ERROR: failed to start task {task_idx}: {e}", file=sys.stderr)
                return 1
            for g in slot:
                assigned.add(g)
            running.append(
                {
                    "proc": proc,
                    "gpus": list(slot),
                    "idx": task_idx,
                    "wdir": str(dir_path),
                }
            )
            stall_start = None
            print(
                f"[flex-gpu] start task {task_idx} CUDA_VISIBLE_DEVICES={cuda_vis} -> {log_file}",
                file=sys.stderr,
            )

        if not pending and not running:
            break

        if pending and not running:
            if stall_start is None:
                stall_start = time.monotonic()
            elif timeout_sec > 0 and (time.monotonic() - stall_start) >= timeout_sec:
                print(
                    "ERROR: flex-gpu timeout: no GPU satisfied min free memory to start next task.",
                    file=sys.stderr,
                )
                return 1
            time.sleep(poll_sec)
        else:
            stall_start = None
            time.sleep(min(2.0, poll_sec))

    print("[flex-gpu] all tasks finished.", file=sys.stderr)
    return max_rc


def create_local_batch_script(work_dirs, np, exe, env_script, gpu_per_task):
    """场景1 & 场景3：生成包含后台并行与 GPU 绑定的本地执行脚本"""
    script_content = ["#!/bin/bash", ""]
    if env_script and Path(env_script).exists():
        script_content.append(f"source {env_script}")
    
    for i, wdir in enumerate(work_dirs):
        dir_path = Path(wdir).resolve()
        log_file = f"vasp_run_{i}.log"
        
        env_vars = ""
        # 场景3: GPU 隔离逻辑
        if gpu_per_task > 0:
            gpu_start = i * gpu_per_task
            gpu_ids = ",".join(str(g) for g in range(gpu_start, gpu_start + gpu_per_task))
            env_vars = f"CUDA_VISIBLE_DEVICES={gpu_ids} "
        
        cmd = f"cd {dir_path} && {env_vars}mpirun -np {np} {exe} > {log_file} 2>&1 &"
        script_content.append(cmd)
    
    script_content.append("wait") # 等待所有后台任务完成
    script_content.append("echo 'All local VASP tasks completed.'")
    return "\n".join(script_content)

def create_slurm_script(work_dirs, np, exe, env_script, template_path):
    """场景2：基于模板生成 Slurm 脚本并提交"""
    if not Path(template_path).exists():
        raise FileNotFoundError(f"Slurm template not found at {template_path}")
        
    with open(template_path, 'r') as f:
        template = f.read()

    # 此处为简化演示，实际可使用 jinja2 或更复杂的替换
    template = template.replace("{{NTASKS}}", str(np))
    
    run_commands = []
    if env_script and Path(env_script).exists():
        run_commands.append(f"source {env_script}")
        
    for wdir in work_dirs:
        dir_path = Path(wdir).resolve()
        run_commands.append(f"cd {dir_path}")
        run_commands.append(f"mpirun -np {np} {exe} > vasp.log")
        run_commands.append("cd - > /dev/null")
        
    template = template.replace("{{COMMANDS}}", "\n".join(run_commands))
    return template

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VASP Task Orchestrator")
    parser.add_argument("--dirs", nargs='+', required=True, help="List of task directories")
    parser.add_argument("--mode", choices=['local', 'slurm'], required=True)
    parser.add_argument("--np", type=int, default=4, help="MPI tasks PER directory")
    parser.add_argument("--exe", type=str, default="vasp_std")
    parser.add_argument("--gpu-per-task", type=int, default=0, help="GPUs to bind per task")
    parser.add_argument("--env-script", type=str, default="")
    parser.add_argument("--slurm-template", type=str, default="")
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
    args = parser.parse_args()

    run_script_path = Path("vasp_orchestration_run.sh")

    if args.mode == "local":
        verify_local_dependencies(args.exe, args.env_script)
        if args.gpu_per_task > 0 and not args.fixed_gpu_layout:
            rc = run_local_gpu_flexible_queue(
                args.dirs,
                args.np,
                args.exe,
                args.env_script,
                args.gpu_per_task,
                args.min_gpu_free_mib,
                max(1.0, args.gpu_ready_poll_sec),
                max(0.0, args.gpu_ready_timeout_sec),
            )
            if rc != 0:
                print(
                    f"ERROR: flex-gpu local run failed (exit code {rc}). "
                    "Check vasp_run_*.log in each task directory.",
                    file=sys.stderr,
                )
                sys.exit(rc)
        else:
            if args.gpu_per_task > 0 and args.fixed_gpu_layout and args.min_gpu_free_mib > 0:
                indices = gpu_indices_for_local_batch(len(args.dirs), args.gpu_per_task)
                wait_for_min_free_gpu_memory(
                    indices,
                    args.min_gpu_free_mib,
                    max(1.0, args.gpu_ready_poll_sec),
                    max(0.0, args.gpu_ready_timeout_sec),
                )
            content = create_local_batch_script(
                args.dirs, args.np, args.exe, args.env_script, args.gpu_per_task
            )
            run_script_path.write_text(content)
            os.chmod(run_script_path, 0o755)
            print(f"Generated local execution script: {run_script_path}")
            print("Starting execution (background tasks managed by wait)...")
            proc = subprocess.run(["bash", run_script_path.name])
            if proc.returncode != 0:
                print(
                    f"ERROR: local orchestration script exited with code {proc.returncode}. "
                    "Check vasp_run_*.log in each task directory and stderr above.",
                    file=sys.stderr,
                )
                sys.exit(proc.returncode)

    elif args.mode == 'slurm':
        content = create_slurm_script(args.dirs, args.np, args.exe, args.env_script, args.slurm_template)
        submit_script = Path("submit_vasp.slurm")
        submit_script.write_text(content)
        print(f"Generated Slurm submission script: {submit_script}")
        print("Submitting to cluster...")
        proc = subprocess.run(["sbatch", submit_script.name])
        if proc.returncode != 0:
            print(f"ERROR: sbatch failed with code {proc.returncode}", file=sys.stderr)
            sys.exit(proc.returncode)