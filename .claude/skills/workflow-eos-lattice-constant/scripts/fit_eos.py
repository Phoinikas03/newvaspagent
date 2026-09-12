#!/usr/bin/env python3
import os
import re
import json
import argparse
import numpy as np
from scipy.optimize import curve_fit

def parse_args():
    parser = argparse.ArgumentParser(description="从 OUTCAR 提取数据并拟合 Birch-Murnaghan 状态方程。")
    parser.add_argument("--dirs", nargs="+", required=True, help="包含 OUTCAR 的目录列表，如 scale_*")
    parser.add_argument("--eos_type", default="birch_murnaghan", help="状态方程类型 (当前支持 birch_murnaghan)")
    parser.add_argument("--reference-poscar", default="POSCAR",
                        help="未缩放参考 POSCAR；存在时用于输出 a_eq 与平衡晶格矢量长度")
    parser.add_argument("--refine-r2-threshold", type=float, default=0.999,
                        help="低于该 R² 时建议在最小点附近二次采样")
    parser.add_argument("--refine-edge-margin", type=float, default=0.20,
                        help="拟合 V0 距采样体积边界小于总体积跨度的该比例时建议补点")
    parser.add_argument("--max-local-scale-interval", type=float, default=0.010,
                        help="平衡点两侧最近 scale 之间的间隔超过该值时建议加密")
    parser.add_argument("--refine-half-width", type=float, default=0.010,
                        help="推荐二次采样 scale 的半宽度")
    parser.add_argument("--refine-step", type=float, default=0.005,
                        help="推荐二次采样 scale 的步长")
    parser.add_argument("--scale-tolerance", type=float, default=5e-4,
                        help="判断推荐 scale 是否已存在时使用的容差")
    return parser.parse_args()

# Birch-Murnaghan 状态方程解析式
def birch_murnaghan(V, E0, V0, B0, B0_prime):
    """
    V: 输入体积
    E0: 平衡能量, V0: 平衡体积
    B0: 体积弹性模量, B0_prime: 体积弹性模量对压力的导数
    """
    eta = (V0 / V)**(2.0 / 3.0)
    E = E0 + 9.0 * V0 * B0 / 16.0 * (
        (eta - 1)**3 * B0_prime +
        (eta - 1)**2 * (6 - 4 * eta)
    )
    return E

def extract_data_from_outcar(outcar_path):
    volume, energy = None, None
    if not os.path.exists(outcar_path):
        return None, None
        
    with open(outcar_path, 'r') as f:
        lines = f.readlines()
        
    # 从后往前找，确保取到的是收敛后的最后一步数据
    for line in reversed(lines):
        if volume is None and "volume of cell :" in line:
            # 解析例如: " volume of cell :      34.1234 "
            volume = float(line.split(":")[1].strip())
        if energy is None and "free  energy" in line and "TOTEN" in line:
            # 解析例如: "  free  energy   TOTEN  =       -24.123456 eV"
            # (不同 VASP 版本在 "energy" 后的空格数可能不同，因此用子串匹配而非固定空格数)
            energy = float(line.split("=")[1].split("eV")[0].strip())
            
        if volume is not None and energy is not None:
            break
            
    return volume, energy

def parse_scale_from_dir(directory):
    basename = os.path.basename(os.path.normpath(directory))
    match = re.search(r"([-+]?\d+(?:\.\d+)?)$", basename)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None

def parse_poscar_lattice(poscar_path):
    if not os.path.exists(poscar_path):
        return None

    with open(poscar_path, "r") as f:
        lines = f.readlines()
    if len(lines) < 5:
        raise ValueError(f"{poscar_path} 不是有效 POSCAR：行数不足。")

    scale = float(lines[1].split()[0])
    raw_vectors = np.array([[float(x) for x in lines[i].split()[:3]] for i in range(2, 5)])
    raw_volume = abs(float(np.linalg.det(raw_vectors)))
    if raw_volume <= 0:
        raise ValueError(f"{poscar_path} 晶格矢量体积非正。")

    if scale < 0:
        factor = (abs(scale) / raw_volume) ** (1.0 / 3.0)
    else:
        factor = scale
    if factor <= 0:
        raise ValueError(f"{poscar_path} POSCAR 缩放因子必须为正，或用负值指定目标体积。")

    lattice = raw_vectors * factor
    lengths = np.linalg.norm(lattice, axis=1)
    volume = abs(float(np.linalg.det(lattice)))
    return {"volume": volume, "lengths": lengths.tolist()}

def infer_reference_volume(volumes, scales):
    usable = [
        volume / (scale ** 3)
        for volume, scale in zip(volumes, scales)
        if scale is not None and scale > 0
    ]
    if not usable:
        return None
    return float(np.median(usable))

def build_refinement_suggestion(scales, center_scale, refine_half_width, refine_step, tolerance):
    if center_scale is None or refine_step <= 0 or refine_half_width <= 0:
        return [], []

    n_steps = int(round(refine_half_width / refine_step))
    suggested = [
        center_scale + i * refine_step
        for i in range(-n_steps, n_steps + 1)
        if center_scale + i * refine_step > 0
    ]
    existing_scales = [scale for scale in scales if scale is not None]
    new_scales = [
        scale for scale in suggested
        if all(abs(scale - existing) > tolerance for existing in existing_scales)
    ]
    return suggested, new_scales

def assess_refinement_need(V, E, V0, r_squared, scales, center_scale, args):
    reasons = []
    min_idx = int(np.argmin(E))

    if r_squared is not None and r_squared < args.refine_r2_threshold:
        reasons.append("R_squared_below_threshold")

    if min_idx == 0 or min_idx == len(E) - 1:
        reasons.append("discrete_minimum_on_boundary")

    v_min = float(np.min(V))
    v_max = float(np.max(V))
    v_span = v_max - v_min
    if v_span > 0:
        if V0 <= v_min or V0 >= v_max:
            reasons.append("fitted_V0_outside_sample_range")
        else:
            edge_margin = min(V0 - v_min, v_max - V0) / v_span
            if edge_margin < args.refine_edge_margin:
                reasons.append("fitted_V0_near_sample_edge")

    existing_scales = sorted({scale for scale in scales if scale is not None})
    if center_scale is not None and len(existing_scales) >= 2:
        lower = [scale for scale in existing_scales if scale < center_scale - args.scale_tolerance]
        upper = [scale for scale in existing_scales if scale > center_scale + args.scale_tolerance]
        if not lower or not upper:
            reasons.append("fitted_scale_not_bracketed")
        else:
            local_interval = min(upper) - max(lower)
            if local_interval > args.max_local_scale_interval + 1e-12:
                reasons.append("local_scale_interval_too_coarse")

    return sorted(set(reasons))

def round_or_none(value, digits):
    if value is None:
        return None
    return round(float(value), digits)

def fit_eos(directories, args):
    records = []

    for d in directories:
        outcar = os.path.join(d, "OUTCAR")
        v, e = extract_data_from_outcar(outcar)
        if v is not None and e is not None:
            records.append({
                "directory": d,
                "volume": v,
                "energy": e,
                "scale": parse_scale_from_dir(d),
            })
        else:
            print(f"警告: 无法从 {outcar} 提取有效的体积或能量。")

    if len(records) < 4:
        raise ValueError("有效数据点不足 4 个，无法拟合 4 参数的 Birch-Murnaghan 方程。")

    records = sorted(records, key=lambda item: item["volume"])
    V = np.array([item["volume"] for item in records])
    E = np.array([item["energy"] for item in records])
    scales = [item["scale"] for item in records]

    # 初始参数猜测 (Initial guesses)
    # 取能量最低点为初始 V0 和 E0
    min_idx = np.argmin(E)
    V0_guess = V[min_idx]
    E0_guess = E[min_idx]
    # 体积弹性模量经验值转换系数 (eV/Angstrom^3 -> GPa) = 160.21766
    B0_guess = 0.5 # 约 80 GPa
    B0_prime_guess = 4.0 

    p0 = [E0_guess, V0_guess, B0_guess, B0_prime_guess]

    # 非线性拟合
    try:
        popt, pcov = curve_fit(birch_murnaghan, V, E, p0=p0, maxfev=10000)
    except Exception as e:
        raise RuntimeError(f"曲线拟合失败: {e}")

    E0, V0, B0, B0_prime = popt
    B0_GPa = B0 * 160.217662 # 单位换算

    # 计算 R-squared 判断拟合优度
    residuals = E - birch_murnaghan(V, *popt)
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((E - np.mean(E))**2)
    r_squared = None if ss_tot == 0 else 1 - (ss_res / ss_tot)

    reference_lattice = parse_poscar_lattice(args.reference_poscar)
    reference_volume = reference_lattice["volume"] if reference_lattice else infer_reference_volume(V, scales)
    linear_scale_eq = None
    lattice_lengths_eq = None
    a_eq = None
    if reference_volume is not None and reference_volume > 0:
        linear_scale_eq = (V0 / reference_volume) ** (1.0 / 3.0)
        if reference_lattice:
            lattice_lengths_eq = [length * linear_scale_eq for length in reference_lattice["lengths"]]
            a_eq = lattice_lengths_eq[0]

    refinement_reasons = assess_refinement_need(V, E, V0, r_squared, scales, linear_scale_eq, args)
    suggested_scales, suggested_new_scales = build_refinement_suggestion(
        scales,
        linear_scale_eq,
        args.refine_half_width,
        args.refine_step,
        args.scale_tolerance,
    )

    results = {
        "V_0_Ang3": round(V0, 4),
        "E_0_eV": round(E0, 6),
        "B_0_GPa": round(B0_GPa, 2),
        "B_0_prime": round(B0_prime, 2),
        "R_squared": round_or_none(r_squared, 6),
        "linear_scale_eq": round_or_none(linear_scale_eq, 6),
        "a_eq_A": round_or_none(a_eq, 6),
        "lattice_lengths_eq_A": (
            [round(float(length), 6) for length in lattice_lengths_eq]
            if lattice_lengths_eq is not None else None
        ),
        "refinement_recommended": bool(refinement_reasons),
        "refinement_reasons": refinement_reasons,
        "suggested_refinement_scales": [round(float(scale), 6) for scale in suggested_scales],
        "suggested_new_refinement_scales": [round(float(scale), 6) for scale in suggested_new_scales],
        "suggested_generation_command": (
            "python scripts/generate_scaled_poscars.py --poscar POSCAR --scales "
            + " ".join(f"{scale:.6f}" for scale in suggested_new_scales)
            if suggested_new_scales else None
        ),
        "data_points": {
            "volumes": V.tolist(),
            "energies": E.tolist(),
            "scales": scales,
            "directories": [item["directory"] for item in records],
        }
    }
    
    # 打印给标准输出，并将 JSON 保存
    print(json.dumps(results, indent=2))
    with open("eos_results.json", 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    args = parse_args()
    fit_eos(args.dirs, args)
