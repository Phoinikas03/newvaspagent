#!/bin/bash
# Local / interactive environment for VASP + MPI.
# 1) 先运行: python .claude/skills/run_vasp/scripts/probe_env.py
#    若 dependencies 中 mpirun_found / vasp_std_found 为 false，在此填写 module / PATH。
# 2) 将本文件复制到工作区或保持 skill 内路径，通过 --env-script 传给 vasp_runner.py / quick_test.py

# module purge
# module load intel/2021.4.0 mpi/2021.4.0 vasp/6.3.2
# export PATH=/path/to/vasp/bin:$PATH

export OMP_NUM_THREADS=1
export I_MPI_FABRICS=shm:ofi
