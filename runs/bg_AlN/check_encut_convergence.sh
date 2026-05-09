#!/bin/bash
while true; do
  all_done=true
  for dir in convergence_test/encut_test/e_*; do
    if grep -q "reached required accuracy" "$dir/OUTCAR" 2>/dev/null; then
      :
    else
      all_done=false
      break
    fi
  done
  
  if [ "$all_done" = true ]; then
    echo "All ENCUT tests converged!"
    break
  fi
  
  sleep 10
done
