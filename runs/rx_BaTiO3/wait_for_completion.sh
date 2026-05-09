#!/bin/bash
OUTCAR="/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BaTiO3/OUTCAR"

echo "Waiting for VASP calculation to complete..."
while true; do
    if grep -q "reached required accuracy" "$OUTCAR" 2>/dev/null; then
        echo "✓ Calculation completed successfully!"
        break
    fi
    
    # 检查是否有错误导致计算停止
    if grep -q "VERY BAD NEWS" "$OUTCAR" 2>/dev/null; then
        echo "✗ Calculation failed with error!"
        break
    fi
    
    # 每30秒检查一次
    sleep 30
done
