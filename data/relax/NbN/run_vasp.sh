#!/bin/bash

timestamp=$(date +"%Y%m%d_%H%M%S")
logname="log_${timestamp}.txt"

source ~/env_vasp
mpirun -n 1 vasp_std >> "$logname" 2>&1
