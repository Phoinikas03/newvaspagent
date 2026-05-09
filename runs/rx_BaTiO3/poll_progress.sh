#!/bin/bash
OUTCAR="/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BaTiO3/OUTCAR"
OSZICAR="/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BaTiO3/OSZICAR"

echo "Starting VASP progress polling (30s interval)..."
last_ionic=0

while true; do
    # 检查是否已收敛
    if grep -q "reached required accuracy" "$OUTCAR" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ✓ CONVERGED - Calculation completed!"
        tail -5 "$OSZICAR" 2>/dev/null | tail -1
        break
    fi
    
    # 检查是否有错误
    if grep -q "VERY BAD NEWS" "$OUTCAR" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ✗ ERROR - Calculation failed!"
        break
    fi
    
    # 获取当前离子步数
    ionic=$(grep -c "^   [0-9]* F=" "$OUTCAR" 2>/dev/null || echo 0)
    
    # 获取最新能量
    energy=$(tail -1 "$OSZICAR" 2>/dev/null | awk '{print $NF}')
    
    # 获取最新迭代
    iter=$(grep "Iteration.*(" "$OUTCAR" 2>/dev/null | tail -1 | sed 's/.*Iteration *\([0-9]*\)(\([0-9]*\)).*/\1(\2)/')
    
    if [ "$ionic" -ne "$last_ionic" ]; then
        echo "[$(date '+%H:%M:%S')] Ionic step $ionic completed, Energy: $energy eV"
        last_ionic=$ionic
    else
        echo "[$(date '+%H:%M:%S')] Ionic: $ionic, Iter: $iter, Energy: $energy eV"
    fi
    
    sleep 30
done
