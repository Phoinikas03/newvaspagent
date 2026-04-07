#!/usr/bin/env python3
import os
import shutil
import subprocess
import argparse
from pathlib import Path

def setup_quick_test_incar(incar_path):
    backup_path = incar_path.with_name("INCAR.bak_test")
    shutil.copy(incar_path, backup_path)
    
    with open(incar_path, "a") as f:
        f.write("\n# --- INJECTED FOR QUICK TEST ---\n")
        f.write("NELM = 5\n")   # 只跑 5 个电子步
        f.write("NSW = 0\n")    # 关闭离子步弛豫
        f.write("NWRITE = 1\n") # 减少输出
    return backup_path

def run_quick_test(work_dir, exe="vasp_std", env_script=""):
    work_dir = Path(work_dir).resolve()
    incar_path = work_dir / "INCAR"
    
    if not incar_path.exists():
        print("Error: INCAR not found.")
        return

    print("Configuring INCAR for quick test (NELM=5, NSW=0)...")
    backup_path = setup_quick_test_incar(incar_path)

    cmd = f"mpirun -np 2 {exe}"
    if env_script and Path(env_script).exists():
        cmd = f"source {env_script} && {cmd}"

    print(f"Executing quick test: {cmd}")
    try:
        subprocess.run(cmd, cwd=work_dir, shell=True, executable="/bin/bash")
        print("\n[Test Finished] Checking OSZICAR for basic electronic convergence starts...")
        if (work_dir / "OSZICAR").exists():
            subprocess.run(["head", "-n", "10", str(work_dir / "OSZICAR")])
    finally:
        print("\nRestoring original INCAR...")
        shutil.move(backup_path, incar_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=str, default=".")
    parser.add_argument("--exe", type=str, default="vasp_std")
    parser.add_argument("--env-script", type=str, default="")
    args = parser.parse_args()
    run_quick_test(args.work_dir, args.exe, args.env_script)