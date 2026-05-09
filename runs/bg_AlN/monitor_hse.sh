#!/bin/bash
start_time=$(date +%s)
while true; do
  if [ -f "hse_calc/OUTCAR" ]; then
    if grep -q "reached required accuracy" hse_calc/OUTCAR 2>/dev/null; then
      end_time=$(date +%s)
      elapsed=$((end_time - start_time))
      echo "✓ HSE06 calculation CONVERGED!"
      echo "Elapsed time: $((elapsed / 60)) minutes $((elapsed % 60)) seconds"
      energy=$(grep "free  energy" hse_calc/OUTCAR | tail -1 | awk '{print $5}')
      echo "Final energy: $energy eV"
      break
    else
      nelm_step=$(grep "^ *[0-9]* *F=" hse_calc/OUTCAR | tail -1 | awk '{print $1}')
      if [ -z "$nelm_step" ]; then
        nelm_step="0"
      fi
      end_time=$(date +%s)
      elapsed=$((end_time - start_time))
      echo "HSE06 running... step $nelm_step/100 (elapsed: $((elapsed / 60))m)"
    fi
  else
    echo "Waiting for OUTCAR..."
  fi
  sleep 30
done
