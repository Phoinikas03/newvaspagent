#!/bin/bash

echo "=== Cu 结构优化计算验证 ==="
echo ""

# 检查计算是否完成
if grep -q "reached required accuracy" OUTCAR; then
    echo "✓ 计算已收敛"
else
    echo "⚠ 计算未完全收敛（可能达到 NSW 上限）"
fi

echo ""
echo "=== 离子步统计 ==="
ionic_steps=$(grep -c "^   [0-9]" OSZICAR)
echo "总离子步数: $ionic_steps"

echo ""
echo "=== 能量收敛趋势 ==="
grep "^   [0-9]" OSZICAR | awk '{printf "Step %d: E = %s eV, dE = %s eV\n", NR, $3, $NF}'

echo ""
echo "=== 最终结构信息 ==="
echo "初始原子数: $(head -7 POSCAR | tail -1)"
echo "最终原子数: $(head -7 CONTCAR | tail -1)"

echo ""
echo "=== 最终能量 ==="
tail -1 OSZICAR

echo ""
echo "=== 力收敛情况 ==="
grep "max\|rms" OUTCAR | tail -5

