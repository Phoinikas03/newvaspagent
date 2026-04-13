#!/bin/bash

source /home/xiazeyu/env_vasp
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260412_110350/convergence_test/kspacing_test/k_0.30 && CUDA_VISIBLE_DEVICES=0 mpirun -np 1 vasp_std > vasp_run_0.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260412_110350/convergence_test/kspacing_test/k_0.25 && CUDA_VISIBLE_DEVICES=1 mpirun -np 1 vasp_std > vasp_run_1.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260412_110350/convergence_test/kspacing_test/k_0.20 && CUDA_VISIBLE_DEVICES=2 mpirun -np 1 vasp_std > vasp_run_2.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260412_110350/convergence_test/kspacing_test/k_0.15 && CUDA_VISIBLE_DEVICES=3 mpirun -np 1 vasp_std > vasp_run_3.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260412_110350/convergence_test/kspacing_test/k_0.10 && CUDA_VISIBLE_DEVICES=4 mpirun -np 1 vasp_std > vasp_run_4.log 2>&1 &
wait
echo 'All local VASP tasks completed.'