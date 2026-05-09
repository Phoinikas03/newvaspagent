#!/bin/bash

source /home/xiazeyu/env_vasp
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260409_143758/scale_0.940 && CUDA_VISIBLE_DEVICES=0 mpirun -np 1 vasp_std > vasp_run_0.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260409_143758/scale_0.960 && CUDA_VISIBLE_DEVICES=1 mpirun -np 1 vasp_std > vasp_run_1.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260409_143758/scale_0.980 && CUDA_VISIBLE_DEVICES=2 mpirun -np 1 vasp_std > vasp_run_2.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260409_143758/scale_1.000 && CUDA_VISIBLE_DEVICES=3 mpirun -np 1 vasp_std > vasp_run_3.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260409_143758/scale_1.020 && CUDA_VISIBLE_DEVICES=4 mpirun -np 1 vasp_std > vasp_run_4.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260409_143758/scale_1.040 && CUDA_VISIBLE_DEVICES=5 mpirun -np 1 vasp_std > vasp_run_5.log 2>&1 &
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260409_143758/scale_1.060 && CUDA_VISIBLE_DEVICES=6 mpirun -np 1 vasp_std > vasp_run_6.log 2>&1 &
wait
echo 'All local VASP tasks completed.'