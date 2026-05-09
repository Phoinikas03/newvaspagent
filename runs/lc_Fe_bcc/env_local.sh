#!/bin/bash
# Local environment for VASP GPU (vasp_std GPU build) on d01
# 8x NVIDIA RTX 3090, GPU-accelerated VASP via NVIDIA HPC SDK

source ~/env_vasp

export OMP_NUM_THREADS=1
