#!/bin/bash
#SBATCH --job-name=VASP_Batch
#SBATCH --nodes=1
#SBATCH --ntasks={{NTASKS}}
#SBATCH --time=24:00:00
#SBATCH --partition=compute

# 你的集群环境变量
# module load vasp

# 下面的命令由 vasp_runner.py 自动注入
{{COMMANDS}}