#!/bin/bash
while true; do
  all_done=true
  for dir in convergence_test/kspacing_test/k_*; do
    if [ -f "$dir/OUTCAR" ]; then
      # 检查是否有最后的能量值
      if ! grep -q "free  energy" "$dir/OUTCAR" 2>/dev/null; then
        all_done=false
        break
      fi
    else
      all_done=false
      break
    fi
  done
  
  if [ "$all_done" = true ]; then
    echo "All KSPACING tests completed!"
    break
  fi
  
  sleep 15
done
