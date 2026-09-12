#!/bin/bash
# Wrapper: VASP environment + the agent's conda env, one system pinned to one GPU.
# Args captured up front: sourcing the Intel/MKL env script clobbers "$@".
ARGS=("$@")
source ~/env_vasp
export OMP_NUM_THREADS=1
source /data/xiazeyu/conda/etc/profile.d/conda.sh
conda activate claude
export PATH="$HOME/.local/bin:$PATH"
exec python /mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc/scripts/run_agent_lc.py "${ARGS[@]}"
