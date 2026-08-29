#!/usr/bin/env python3
import os
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="批量生成各向同性缩放的 POSCAR 用于 EOS 测试。")
    parser.add_argument("--poscar", default="POSCAR", help="初始 POSCAR 文件的路径")
    parser.add_argument("--scales", nargs="+", type=float,
                        help="缩放因子列表，如 0.96 0.98 1.00 1.02 1.04")
    parser.add_argument("--center-scale", type=float,
                        help="围绕该线性缩放因子生成等间隔加密采样点")
    parser.add_argument("--step", type=float,
                        help="与 --center-scale 或 --min-scale/--max-scale 配合使用的线性缩放步长")
    parser.add_argument("--points", type=int, default=5,
                        help="围绕 --center-scale 生成的点数，建议使用奇数以包含中心点")
    parser.add_argument("--min-scale", type=float, help="按范围生成采样点的最小线性缩放因子")
    parser.add_argument("--max-scale", type=float, help="按范围生成采样点的最大线性缩放因子")
    parser.add_argument("--prefix", default="scale", help="输出目录前缀，默认生成 scale_*.xxx")
    parser.add_argument("--dir-decimals", type=int, default=3,
                        help="目录名中缩放因子保留的小数位数，默认 3")
    return parser.parse_args()

def build_scales(args):
    if args.scales:
        return args.scales

    if args.center_scale is not None:
        if args.step is None or args.step <= 0:
            raise ValueError("使用 --center-scale 时必须提供正的 --step。")
        if args.points <= 0:
            raise ValueError("--points 必须为正整数。")
        if args.points % 2 == 0:
            raise ValueError("--points 建议为奇数，以便包含中心缩放因子。")
        half = args.points // 2
        return [args.center_scale + (i - half) * args.step for i in range(args.points)]

    if args.min_scale is not None or args.max_scale is not None:
        if args.min_scale is None or args.max_scale is None:
            raise ValueError("--min-scale 与 --max-scale 必须同时提供。")
        if args.step is None or args.step <= 0:
            raise ValueError("使用 --min-scale/--max-scale 时必须提供正的 --step。")
        if args.min_scale > args.max_scale:
            raise ValueError("--min-scale 不能大于 --max-scale。")
        n_steps = int(round((args.max_scale - args.min_scale) / args.step))
        scales = [args.min_scale + i * args.step for i in range(n_steps + 1)]
        if scales[-1] < args.max_scale - 1e-10:
            scales.append(args.max_scale)
        return scales

    raise ValueError("必须提供 --scales，或提供 --center-scale/--step，或提供 --min-scale/--max-scale/--step。")

def generate_scaled_poscars(base_poscar, scales, prefix="scale", dir_decimals=3):
    if not os.path.exists(base_poscar):
        raise FileNotFoundError(f"未找到基础文件: {base_poscar}")

    with open(base_poscar, 'r') as f:
        lines = f.readlines()

    # POSCAR 的第二行是全局缩放因子
    try:
        base_scale = float(lines[1].strip())
    except ValueError:
        raise ValueError("POSCAR 第二行不是有效的数字（期望全局缩放因子）。")

    seen_dirs = set()
    for scale in scales:
        dir_name = f"{prefix}_{scale:.{dir_decimals}f}"
        if dir_name in seen_dirs:
            print(f"跳过重复目录名: {dir_name} (缩放因子: {scale:.8f})")
            continue
        seen_dirs.add(dir_name)
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
    scales = build_scales(args)
    generate_scaled_poscars(args.poscar, scales, prefix=args.prefix, dir_decimals=args.dir_decimals)
