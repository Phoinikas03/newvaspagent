#!/bin/bash

source /home/xiazeyu/env_vasp
cd /mnt/data_x3/xiazeyu/newvaspagent/runs/20260410_121747 && CUDA_VISIBLE_DEVICES=0 mpirun -np 1 vasp_std > vasp_run_0.log 2>&1 &
wait
echo 'All local VASP tasks completed.'