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
        if energy is None and "free  energy   TOTEN  =" in line:
            # 解析例如: "  free  energy   TOTEN  =       -24.123456 eV"
            energy = float(line.split("=")[1].split("eV")[0].strip())
            
        if volume is not None and energy is not None:
            break
            
    return volume, energy

def fit_eos(directories):
    volumes = []
    energies = []
    
    for d in directories:
        outcar = os.path.join(d, "OUTCAR")
        v, e = extract_data_from_outcar(outcar)
        if v is not None and e is not None:
            volumes.append(v)
            energies.append(e)
        else:
            print(f"警告: 无法从 {outcar} 提取有效的体积或能量。")

    if len(volumes) < 4:
        raise ValueError("有效数据点不足 4 个，无法拟合 4 参数的 Birch-Murnaghan 方程。")

    V = np.array(volumes)
    E = np.array(energies)

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
    r_squared = 1 - (ss_res / ss_tot)

    results = {
        "V_0_Ang3": round(V0, 4),
        "E_0_eV": round(E0, 6),
        "B_0_GPa": round(B0_GPa, 2),
        "B_0_prime": round(B0_prime, 2),
        "R_squared": round(r_squared, 6),
        "data_points": {
            "volumes": V.tolist(),
            "energies": E.tolist()
        }
    }
    
    # 打印给标准输出，并将 JSON 保存
    print(json.dumps(results, indent=2))
    with open("eos_results.json", 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    args = parse_args()
    fit_eos(args.dirs)