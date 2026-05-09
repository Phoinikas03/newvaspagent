#!/bin/bash
while true; do
  if [ -f "pbe_scf/OUTCAR" ]; then
    if grep -q "reached required accuracy" pbe_scf/OUTCAR 2>/dev/null; then
      echo "✓ PBE calculation CONVERGED!"
      energy=$(grep "free  energy" pbe_scf/OUTCAR | tail -1 | awk '{print $5}')
      echo "Final energy: $energy eV"
      break
    else
      nelm_step=$(grep "^ *[0-9]* *F=" pbe_scf/OUTCAR | tail -1 | awk '{print $1}')
      if [ -z "$nelm_step" ]; then
        nelm_step="0"
      fi
      echo "PBE running... step $nelm_step/100"
    fi
  else
    echo "Waiting for OUTCAR..."
  fi
  sleep 20
done
