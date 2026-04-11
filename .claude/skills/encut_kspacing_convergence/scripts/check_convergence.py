#!/usr/bin/env python3
import os
import argparse
import json

def parse_args():
    parser = argparse.ArgumentParser(description="检查 VASP OUTCAR 的收敛状态。")
    parser.add_argument("directory", help="包含 OUTCAR 的目标文件夹")
    return parser.parse_args()

def check_outcar(directory):
    outcar_path = os.path.join(directory, "OUTCAR")
    
    result = {
        "job_completed": False,
        "electronic_converged": False,
        "details": ""
    }

    if not os.path.exists(outcar_path):
        result["details"] = f"未找到文件: {outcar_path}"
        print(json.dumps(result, indent=2))
        return

    with open(outcar_path, 'r') as f:
        lines = f.readlines()

    # 1. 检查是否正常结束 (看末尾是否有耗时统计)
    for line in lines[-50:]:
        if "General timing and accounting informations" in line or "Voluntary context switches" in line:
            result["job_completed"] = True
            break

    # 2. 检查电子步是否收敛
    # 寻找诸如 "aborting loop because EDIFF is reached" 的标志
    # 或者检查最后一次 SCF 循环是否达到了 NELM (默认 60)
    for line in reversed(lines):
        if "aborting loop because EDIFF is reached" in line:
            result["electronic_converged"] = True
            result["details"] = "达到设定的 EDIFF 精度，电子步收敛。"
            break
        if "Iteration" in line and "SCF" not in line: 
            # 匹配类似于: "       Iteration    60(  60)"
            try:
                parts = line.split()
                if "Iteration" in parts:
                    iter_idx = parts.index("Iteration")
                    current_step = int(parts[iter_idx+1].split('(')[0])
                    # VASP 默认最大电子步通常是 60，通过对比当前步数可辅助判断，
                    # 但更稳妥的是如果没有找到 aborting loop 且跑完了，多半是未收敛。
            except:
                pass
            
    if result["job_completed"] and not result["electronic_converged"]:
        result["details"] = "任务已结束，但未能达到 EDIFF 收敛标准，可能遇到了电子步震荡。"
    elif not result["job_completed"]:
        result["details"] = "OUTCAR 缺少正常的结束标志，任务可能被中途 Kill 或仍在运行中。"

    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    args = parse_args()
    check_outcar(args.directory)
