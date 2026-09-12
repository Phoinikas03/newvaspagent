#!/usr/bin/env python
"""atomate2 arm of the Sol27LC end-to-end baseline.

One system per invocation, pinned to a single GPU, so that both arms get the
same hardware quota (1 MPI rank <-> 1 GPU). Everything about the calculation
protocol -- ENCUT, k-spacing, smearing, pseudopotential variant, strain window
-- comes from atomate2's own MPGGAEos input sets; the only thing overridden is
the pseudopotential *library* version, because this machine carries
POT_GGA_PAW_PBE and atomate2 defaults to PBE_54.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path

REPO = Path("/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent")
EXP = REPO / "rev_sol27lc"
POTCAR_LIB = REPO / "POTCAR_dir"
# The one human override, recorded as specification cost: atomate2 asks for
# PBE_54, this site only has the base PBE library (the same one the agent used).
POTCAR_FUNCTIONAL = "PBE"


def apply_potcar_functional(maker, functional: str, seen=None) -> int:
    """Recursively set user_potcar_functional on every input-set generator."""
    import dataclasses

    seen = seen if seen is not None else set()
    if id(maker) in seen or not dataclasses.is_dataclass(maker):
        return 0
    seen.add(id(maker))

    count = 0
    generator = getattr(maker, "input_set_generator", None)
    if generator is not None and hasattr(generator, "user_potcar_functional"):
        generator.user_potcar_functional = functional
        count += 1
    for field in dataclasses.fields(maker):
        count += apply_potcar_functional(getattr(maker, field.name), functional, seen)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True, help="e.g. Si_dia")
    parser.add_argument("--gpu-uuid", required=True, help="GPU UUID from nvidia-smi -L")
    parser.add_argument("--outroot", default=str(EXP / "runs_atomate2"))
    args = parser.parse_args()

    workdir = Path(args.outroot) / args.system
    workdir.mkdir(parents=True, exist_ok=True)

    os.environ["PMG_VASP_PSP_DIR"] = str(POTCAR_LIB)
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu_uuid
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ.setdefault("ATOMATE2_VASP_CMD", "mpirun -np 1 vasp_gpu")

    from jobflow import run_locally
    from pymatgen.core import Structure
    from atomate2.vasp.flows.eos import MPGGAEosMaker

    structure = Structure.from_file(EXP / "data" / args.system / "POSCAR")
    maker = MPGGAEosMaker()
    n_overridden = apply_potcar_functional(maker, POTCAR_FUNCTIONAL)

    meta = {
        "system": args.system,
        "gpu_uuid": args.gpu_uuid,
        "vasp_cmd": os.environ["ATOMATE2_VASP_CMD"],
        "potcar_functional_override": POTCAR_FUNCTIONAL,
        "generators_overridden": n_overridden,
        "linear_strain": list(maker.linear_strain),
        "number_of_frames": maker.number_of_frames,
        "atomate2_maker": maker.name,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (workdir / "run_meta.json").write_text(json.dumps(meta, indent=2))

    flow = maker.make(structure)
    started = time.time()
    status = "completed"
    try:
        responses = run_locally(
            flow,
            create_folders=True,
            root_dir=str(workdir),
            ensure_success=False,
            raise_immediately=False,
        )
        (workdir / "responses.json").write_text(
            json.dumps({str(k): str(v) for k, v in responses.items()}, indent=2)
        )
    except Exception:
        status = "exception"
        (workdir / "exception.txt").write_text(traceback.format_exc())

    meta.update(
        finished=time.strftime("%Y-%m-%dT%H:%M:%S"),
        wall_seconds=round(time.time() - started, 1),
        status=status,
    )
    (workdir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
