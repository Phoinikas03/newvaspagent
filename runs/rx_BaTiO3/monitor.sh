#!/bin/bash
OUTCAR="/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BaTiO3/OUTCAR"
OSZICAR="/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BaTiO3/OSZICAR"

echo "=== VASP Relaxation Monitor ==="
echo "Time: $(date)"

# 检查离子步数
ionic_steps=$(grep -c "ionic step" "$OUTCAR" 2>/dev/null || echo 0)
echo "Ionic steps completed: $ionic_steps"

# 检查最新能量
if [ -f "$OSZICAR" ]; then
    tail -1 "$OSZICAR" | awk '{print "Latest energy: " $5 " eV"}'
fi

# 检查最大力
max_force=$(grep "max(force)" "$OUTCAR" 2>/dev/null | tail -1 | awk '{print $NF}')
if [ -n "$max_force" ]; then
    echo "Max force: $max_force eV/Å"
fi

# 检查是否收敛
if grep -q "reached required accuracy" "$OUTCAR" 2>/dev/null; then
    echo "Status: ✓ CONVERGED"
else
    echo "Status: Running..."
fi
