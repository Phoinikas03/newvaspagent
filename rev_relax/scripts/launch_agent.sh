#!/bin/bash
# Wrapper: VASP environment + the agent's conda env, one system pinned to one GPU.
# Same as rev_sol27lc/scripts/launch_agent.sh; only the driver differs.
# Args captured up front: sourcing the Intel/MKL env script clobbers "$@".
ARGS=("$@")
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$HERE/../.." && pwd -P)"
[ -f "$REPO/site.env" ] && source "$REPO/site.env"
source "${VASP_ENV_SCRIPT:-$HOME/env_vasp}"
export OMP_NUM_THREADS=1
CONDA_PREFIX_AGENT="${VASPAGENT_CONDA_PREFIX:-/data/xiazeyu/conda/envs/claude}"
export PATH="$CONDA_PREFIX_AGENT/bin:$HOME/.local/bin:$PATH"
export VASP_BIN_DIR="$(dirname "$(command -v vasp_std)")"
exec python "$HERE/run_agent_relax.py" "${ARGS[@]}"
