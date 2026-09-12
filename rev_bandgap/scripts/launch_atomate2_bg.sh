#!/bin/bash
# Wrapper: VASP environment + atomate2 env, one material pinned to one GPU.
# Args captured up front: sourcing the Intel/MKL env script clobbers "$@".
ARGS=("$@")
source ~/env_vasp
export OMP_NUM_THREADS=1
source /data/xiazeyu/conda/etc/profile.d/conda.sh
conda activate /mnt/data_x3/xiazeyu/conda-envs/atomate2
export PYTHONWARNINGS=ignore
exec python /mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap/scripts/run_atomate2_bg.py "${ARGS[@]}"
