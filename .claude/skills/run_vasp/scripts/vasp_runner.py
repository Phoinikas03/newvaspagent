#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path

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

    if args.mode == 'local':
        content = create_local_batch_script(args.dirs, args.np, args.exe, args.env_script, args.gpu_per_task)
        run_script_path.write_text(content)
        os.chmod(run_script_path, 0o755)
        print(f"Generated local execution script: {run_script_path}")
        print("Starting execution (background tasks managed by wait)...")
        subprocess.run(["bash", run_script_path.name])
        
    elif args.mode == 'slurm':
        content = create_slurm_script(args.dirs, args.np, args.exe, args.env_script, args.slurm_template)
        submit_script = Path("submit_vasp.slurm")
        submit_script.write_text(content)
        print(f"Generated Slurm submission script: {submit_script}")
        print("Submitting to cluster...")
        subprocess.run(["sbatch", submit_script.name])