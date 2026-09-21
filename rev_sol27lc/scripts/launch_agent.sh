#!/bin/bash
# Wrapper: VASP environment + the agent's conda env, one system pinned to one GPU.
# Args captured up front: sourcing the Intel/MKL env script clobbers "$@".
#
# Machine-specific locations live in <repo>/site.env (untracked; see
# site.env.example). Defaults below reproduce the d01 setup used for rep1.
ARGS=("$@")
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$HERE/../.." && pwd -P)"
[ -f "$REPO/site.env" ] && source "$REPO/site.env"
source "${VASP_ENV_SCRIPT:-$HOME/env_vasp}"
export OMP_NUM_THREADS=1
CONDA_PREFIX_AGENT="${VASPAGENT_CONDA_PREFIX:-/data/xiazeyu/conda/envs/claude}"
# Equivalent to `conda activate` for this purpose: the env's bin first, so the
# agent's own `python ...vasp_runner.py` calls resolve to the same interpreter.
export PATH="$CONDA_PREFIX_AGENT/bin:$HOME/.local/bin:$PATH"
export VASP_BIN_DIR="$(dirname "$(command -v vasp_std)")"
exec python "$HERE/run_agent_lc.py" "${ARGS[@]}"
