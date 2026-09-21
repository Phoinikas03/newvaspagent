#!/bin/bash
# List every question currently waiting for an operator reply.
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
found=0
for q in "$EXP"/runs_agent/*/*/PENDING_QUESTION.md; do
  [ -f "$q" ] || continue
  found=1
  d=$(dirname "$q")
  echo "############ $(basename "$(dirname "$d")")/$(basename "$d")"
  cat "$q"
  echo "---- reply with: echo '<answer>' > $d/OPERATOR_ANSWER.txt"
  echo
done
[ $found -eq 0 ] && echo "(no pending questions)"
