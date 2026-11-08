#!/bin/bash
cd /tmp/terminal-bench-2
OK=0; FAIL=0; FAILED=""
for T in $(ls -d */ | tr -d '/'); do
  [ -f "$T/environment/Dockerfile" ] || continue
  docker build -q -t "tb2-arm64/$T:latest" "$T/environment/" > /data2/gxw/tb2-logs/b-$T.log 2>&1
  if [ $? -eq 0 ]; then OK=$((OK+1)); else FAIL=$((FAIL+1)); FAILED="$FAILED $T"; fi
  echo "$(date +%H:%M:%S) done: $T (ok=$OK fail=$FAIL)"
done
echo "BATCH-DONE ok=$OK fail=$FAIL"
echo "FAILED:$FAILED" > /data2/gxw/tb2-failed.txt
