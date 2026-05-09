#!/usr/bin/env python3
"""
Cu 结构优化结果分析脚本
"""
import os
import re
from pathlib import Path

def parse_oszicar(filepath):
    """解析 OSZICAR 文件"""
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('   '):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        step = int(parts[0])
                        energy = float(parts[2])
                        de = float(parts[-1])
                        data.append({'step': step, 'energy': energy, 'dE': de})
                    except ValueError:
                        pass
    return data

def parse_outcar_convergence(filepath):
    """从 OUTCAR 中提取收敛信息"""
    converged = False
    final_energy = None
    max_force = None
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if 'reached required accuracy' in line:
                converged = True
            if 'Free energy of the ion-electron system' in line:
                # 下一行应该是能量
                idx = lines.index(line)
                if idx + 1 < len(lines):
                    final_energy = lines[idx + 1]
    
    return converged, final_energy

def main():
    workdir = Path('/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_Cu')
    
    print("=" * 60)
    print("Cu 结构优化计算分析")
    print("=" * 60)
    print()
    
    # 解析 OSZICAR
    oszicar_data = parse_oszicar(workdir / 'OSZICAR')
    if oszicar_data:
        print(f"✓ 离子步数: {len(oszicar_data)}")
        print()
        print("能量收敛趋势:")
        print("-" * 60)
        for d in oszicar_data:
            print(f"  Step {d['step']:2d}: E = {d['energy']:15.8f} eV, dE = {d['dE']:12.6e} eV")
        print()
        
        # 计算能量变化
        if len(oszicar_data) > 1:
            de_total = oszicar_data[-1]['energy'] - oszicar_data[0]['energy']
            print(f"总能量变化: {de_total:.8f} eV")
            print()
    
    # 检查收敛状态
    converged, final_energy = parse_outcar_convergence(workdir / 'OUTCAR')
    if converged:
        print("✓ 计算已收敛")
    else:
        print("⚠ 计算未完全收敛（可能达到 NSW 上限）")
    print()
    
    # 检查文件大小
    print("输出文件大小:")
    print("-" * 60)
    for fname in ['OUTCAR', 'OSZICAR', 'CONTCAR', 'vasprun.xml']:
        fpath = workdir / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024 * 1024)
            print(f"  {fname:15s}: {size_mb:8.2f} MB")
    print()

if __name__ == '__main__':
    main()
