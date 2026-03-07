"""
从 OUTCAR 和 CONTCAR 提取结构松弛的关键结果，输出 JSON 报告。
用法: python scripts/analyze_result.py [工作目录]
默认目录: 当前目录

输出字段说明:
  final_energy_eV       - 最终总能量 (eV)
  final_energy_per_atom - 每原子能量 (eV/atom)
  num_atoms             - 原子总数
  max_force_eV_A        - 最终最大原子力 (eV/Å)
  rms_force_eV_A        - 最终 RMS 力 (eV/Å)
  pressure_kbar         - 最终压力 (kBar)
  volume_A3             - 最终晶胞体积 (Å³)
  contcar_path          - CONTCAR 文件路径
"""
import sys
import os
import re
import json


def analyze_result(work_dir="."):
    result = {
        "final_energy_eV": None,
        "final_energy_per_atom": None,
        "num_atoms": None,
        "max_force_eV_A": None,
        "rms_force_eV_A": None,
        "pressure_kbar": None,
        "volume_A3": None,
        "contcar_path": None,
    }

    outcar_path = os.path.join(work_dir, "OUTCAR")
    contcar_path = os.path.join(work_dir, "CONTCAR")

    if os.path.exists(contcar_path) and os.path.getsize(contcar_path) > 0:
        result["contcar_path"] = os.path.abspath(contcar_path)

    if not os.path.exists(outcar_path):
        result["error"] = "OUTCAR 文件不存在"
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    with open(outcar_path, "r", errors="replace") as f:
        content = f.read()
        lines = content.splitlines()

    # 原子数
    m = re.search(r"NIONS\s*=\s*(\d+)", content)
    if m:
        result["num_atoms"] = int(m.group(1))

    # 最终总能量（取最后一次出现）
    energies = re.findall(r"free  energy   TOTEN\s*=\s*([\-\d.]+)\s*eV", content)
    if energies:
        e = float(energies[-1])
        result["final_energy_eV"] = e
        if result["num_atoms"]:
            result["final_energy_per_atom"] = round(e / result["num_atoms"], 6)

    # 最终最大力和 RMS 力（取最后一次出现）
    forces = re.findall(r"FORCES: max atom, RMS\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)", content)
    if forces:
        result["max_force_eV_A"] = float(forces[-1][0])
        result["rms_force_eV_A"] = float(forces[-1][1])

    # 最终压力（取最后一次出现）
    pressures = re.findall(r"external pressure\s*=\s*([\-\d.]+)\s*kB", content)
    if pressures:
        result["pressure_kbar"] = float(pressures[-1])

    # 最终晶胞体积（取最后一次出现）
    volumes = re.findall(r"volume of cell\s*:\s*([\d.]+)", content)
    if volumes:
        result["volume_A3"] = float(volumes[-1])

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    work_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    analyze_result(work_dir)
