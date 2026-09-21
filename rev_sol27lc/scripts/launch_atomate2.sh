#!/bin/bash
# Wrapper: VASP environment + atomate2 env, one system pinned to one GPU.
# Args are captured up front: sourcing the Intel/MKL env script clobbers "$@".
# Machine-specific locations live in <repo>/site.env (see site.env.example).
ARGS=("$@")
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$HERE/../.." && pwd -P)"
[ -f "$REPO/site.env" ] && source "$REPO/site.env"
source "${VASP_ENV_SCRIPT:-$HOME/env_vasp}"
export OMP_NUM_THREADS=1
CONDA_PREFIX_A2="${ATOMATE2_CONDA_PREFIX:-/mnt/data_x3/xiazeyu/conda-envs/atomate2}"
export PATH="$CONDA_PREFIX_A2/bin:$PATH"
export PYTHONWARNINGS=ignore
exec python "$HERE/run_atomate2.py" "${ARGS[@]}"
