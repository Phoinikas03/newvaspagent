#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import shlex
import shutil
from pathlib import Path


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
    args = parser.parse_args()

    run_script_path = Path("vasp_orchestration_run.sh")

    if args.mode == "local":
        verify_local_dependencies(args.exe, args.env_script)
        content = create_local_batch_script(args.dirs, args.np, args.exe, args.env_script, args.gpu_per_task)
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