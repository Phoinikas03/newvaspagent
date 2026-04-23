#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

STATE_FILE_NAME = ".vasp_run_state.json"


def utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        raise FileNotFoundError(f"state file not found: {state_path}")
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(state_path: Path, data: dict) -> None:
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(state_path)


def resolve_state_path(work_dir: str = "", state_file: str = "") -> Path:
    if state_file:
        return Path(state_file).resolve()
    if not work_dir:
        raise ValueError("either --work-dir or --state-file is required")
    return Path(work_dir).resolve() / STATE_FILE_NAME


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


def list_pids_in_pgid(pgid: int | None) -> list[int]:
    if not pgid or pgid <= 0:
        return []
    proc = subprocess.run(
        ["ps", "-o", "pid=", "-g", str(pgid)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    out: list[int] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(int(line))
        except ValueError:
            continue
    return out


def read_proc_cwd(pid: int) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def read_proc_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def verify_local_ownership(state: dict) -> tuple[int, int]:
    pid = state.get("pid")
    pgid = state.get("pgid")
    workdir = str(state.get("workdir", ""))
    launch_cmd = str(state.get("launch_cmd", ""))
    if not pid or not pgid:
        raise RuntimeError("state file does not contain pid/pgid for local termination")
    if not pid_is_alive(pid):
        raise RuntimeError(f"recorded pid is not alive: {pid}")
    pids = list_pids_in_pgid(pgid)
    if not pids:
        raise RuntimeError(f"no live processes found for recorded pgid {pgid}")
    cwd = read_proc_cwd(pid)
    cmdline = read_proc_cmdline(pid)
    if cwd and os.path.realpath(cwd) == os.path.realpath(workdir):
        return pid, pgid
    if workdir and (workdir in cmdline or workdir in launch_cmd):
        return pid, pgid
    raise RuntimeError(
        "unable to prove process ownership from cwd/cmdline; "
        f"pid={pid} pgid={pgid} cwd={cwd!r} cmdline={cmdline!r}"
    )


def wait_for_pgid_exit(pgid: int, timeout_sec: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while True:
        if not list_pids_in_pgid(pgid):
            return True
        if timeout_sec <= 0:
            return False
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)


def terminate_local_run(state_path: Path, state: dict, reason: str, wait_sec: float) -> int:
    pid, pgid = verify_local_ownership(state)
    print(
        f"Terminating local run: run_id={state.get('run_id')} pid={pid} pgid={pgid} workdir={state.get('workdir')}"
    )
    os.killpg(pgid, signal.SIGTERM)
    exited = wait_for_pgid_exit(pgid, wait_sec)
    escalated = False
    if not exited:
        os.killpg(pgid, signal.SIGKILL)
        escalated = True
        exited = wait_for_pgid_exit(pgid, 5.0)
    if not exited:
        raise RuntimeError(f"process group {pgid} still appears alive after SIGTERM/SIGKILL")
    state.update(
        {
            "status": "terminated",
            "ended_at": utc_now_iso(),
            "returncode": None,
            "termination_reason": reason,
            "terminated_via": "SIGKILL" if escalated else "SIGTERM",
        }
    )
    write_state(state_path, state)
    print(
        f"Termination complete: run_id={state.get('run_id')} method={state.get('terminated_via')}"
    )
    return 0


def slurm_job_is_active(job_id: str) -> bool:
    if not job_id:
        return False
    if not shutil_which("squeue"):
        return True
    proc = subprocess.run(
        ["squeue", "-h", "-j", str(job_id), "-o", "%T"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return True
    states = [line.strip().upper() for line in proc.stdout.splitlines() if line.strip()]
    return any(
        state not in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL"}
        for state in states
    )


def shutil_which(name: str) -> str | None:
    proc = subprocess.run(["bash", "-lc", f"command -v {name}"], capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    path = proc.stdout.strip()
    return path or None


def terminate_slurm_run(state_path: Path, state: dict, reason: str) -> int:
    job_id = str(state.get("scheduler_job_id") or "")
    if not job_id:
        raise RuntimeError("state file does not contain scheduler_job_id for slurm termination")
    if not shutil_which("scancel"):
        raise RuntimeError("scancel not found; cannot safely terminate slurm job")
    if not slurm_job_is_active(job_id):
        raise RuntimeError(f"recorded slurm job no longer appears active: {job_id}")
    print(
        f"Terminating slurm run: run_id={state.get('run_id')} job_id={job_id} workdir={state.get('workdir')}"
    )
    proc = subprocess.run(["scancel", job_id], capture_output=True, text=True)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"scancel failed for job {job_id}: {detail}")
    state.update(
        {
            "status": "terminated",
            "ended_at": utc_now_iso(),
            "termination_reason": reason,
            "terminated_via": "scancel",
        }
    )
    write_state(state_path, state)
    print(f"Termination complete: run_id={state.get('run_id')} method=scancel")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely terminate a VASP run started by vasp_runner.py")
    parser.add_argument("--work-dir", type=str, default="", help="Task work directory containing .vasp_run_state.json")
    parser.add_argument("--state-file", type=str, default="", help="Explicit state file path")
    parser.add_argument("--reason", type=str, default="terminated via terminate.py")
    parser.add_argument(
        "--term-wait-sec",
        type=float,
        default=10.0,
        help="Seconds to wait after SIGTERM before escalating to SIGKILL for local runs",
    )
    args = parser.parse_args()

    state_path = resolve_state_path(args.work_dir, args.state_file)
    state = load_state(state_path)
    mode = str(state.get("mode", "")).lower()
    if mode == "local":
        return terminate_local_run(state_path, state, args.reason, args.term_wait_sec)
    if mode == "slurm":
        return terminate_slurm_run(state_path, state, args.reason)
    raise RuntimeError(f"unsupported or missing run mode in state file: {mode!r}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
