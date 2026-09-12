#!/usr/bin/env python
"""atomate2 arm of the band-gap pilot.

One material per invocation, pinned to a single GPU, matching what the agent arm
effectively used: it was allocated seven GPUs but chose KPAR=1 for all five
materials, so both arms consume one GPU per material and their GPU-hours are
directly comparable.

The flow is atomate2's own HSEBandStructureMaker at its default settings. The
only thing overridden is the pseudopotential *library* version, because this
machine carries POT_GGA_PAW_PBE while atomate2 defaults to PBE_54.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path

REPO = Path("/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent")
EXP = REPO / "rev_bandgap"
POTCAR_LIB = REPO / "POTCAR_dir"
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
    parser.add_argument("--material", required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--outroot", default=str(EXP / "runs_atomate2"))
    parser.add_argument("--bandstructure-type", default="both",
                        help="atomate2 default is 'both' (static + uniform + line)")
    args = parser.parse_args()

    workdir = Path(args.outroot) / args.material
    workdir.mkdir(parents=True, exist_ok=True)

    os.environ["PMG_VASP_PSP_DIR"] = str(POTCAR_LIB)
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu_uuid
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ.setdefault("ATOMATE2_VASP_CMD", "mpirun -np 1 vasp_gpu")

    from jobflow import run_locally
    from pymatgen.core import Structure
    from atomate2.vasp.flows.core import HSEBandStructureMaker

    structure = Structure.from_file(EXP / "data" / args.material / "POSCAR")
    maker = HSEBandStructureMaker(bandstructure_type=args.bandstructure_type)
    n_overridden = apply_potcar_functional(maker, POTCAR_FUNCTIONAL)

    meta = {
        "material": args.material,
        "gpu_uuid": args.gpu_uuid,
        "vasp_cmd": os.environ["ATOMATE2_VASP_CMD"],
        "potcar_functional_override": POTCAR_FUNCTIONAL,
        "generators_overridden": n_overridden,
        "bandstructure_type": args.bandstructure_type,
        "atomate2_maker": maker.name,
        "natoms": len(structure),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (workdir / "run_meta.json").write_text(json.dumps(meta, indent=2))

    flow = maker.make(structure)
    started = time.time()
    status = "completed"
    try:
        responses = run_locally(flow, create_folders=True, root_dir=str(workdir),
                                ensure_success=False, raise_immediately=False)
        (workdir / "responses.json").write_text(
            json.dumps({str(k): str(v) for k, v in responses.items()}, indent=2))
    except Exception:
        status = "exception"
        (workdir / "exception.txt").write_text(traceback.format_exc())

    meta.update(finished=time.strftime("%Y-%m-%dT%H:%M:%S"),
                wall_seconds=round(time.time() - started, 1), status=status)
    (workdir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
