#!/usr/bin/env python3
import os
import argparse
import shutil

def parse_args():
    parser = argparse.ArgumentParser(description="批量生成各向同性缩放的 POSCAR 用于 EOS 测试。")
    parser.add_argument("--poscar", default="POSCAR", help="初始 POSCAR 文件的路径")
    parser.add_argument("--scales", nargs="+", type=float, required=True, 
                        help="缩放因子列表，如 0.96 0.98 1.00 1.02 1.04")
    return parser.parse_args()

def generate_scaled_poscars(base_poscar, scales):
    if not os.path.exists(base_poscar):
        raise FileNotFoundError(f"未找到基础文件: {base_poscar}")

    with open(base_poscar, 'r') as f:
        lines = f.readlines()

    # POSCAR 的第二行是全局缩放因子
    try:
        base_scale = float(lines[1].strip())
    except ValueError:
        raise ValueError("POSCAR 第二行不是有效的数字（期望全局缩放因子）。")

    for scale in scales:
        dir_name = f"scale_{scale:.3f}"
        os.makedirs(dir_name, exist_ok=True)
        
        # 计算新的缩放因子 (线性缩放，体积缩放将是此因子的三次方)
        new_scale = base_scale * scale
        
        # 复制修改后的行
        new_lines = lines.copy()
        new_lines[1] = f" {new_scale:.10f}\n"
        
        # 写入子目录
        target_path = os.path.join(dir_name, "POSCAR")
        with open(target_path, 'w') as f:
            f.writelines(new_lines)
            
        print(f"已生成: {target_path} (缩放因子: {scale:.3f})")

if __name__ == "__main__":
    args = parse_args()
    generate_scaled_poscars(args.poscar, args.scales)