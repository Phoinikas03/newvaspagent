#!/bin/bash
# Wrapper: VASP environment + agent conda env. Args captured before sourcing,
# because the Intel/MKL env script clobbers "$@".
ARGS=("$@")
source ~/env_vasp
export OMP_NUM_THREADS=1
source /data/xiazeyu/conda/etc/profile.d/conda.sh
conda activate claude
export PATH="$HOME/.local/bin:$PATH"
exec python /mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_bandgap/scripts/run_agent_bg.py "${ARGS[@]}"
