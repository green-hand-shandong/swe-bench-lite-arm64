#!/bin/bash
# 用法: build-repo.sh <ctx_dir> <tag_prefix> <pass_file> <fail_file>
CTX=$1; PREFIX=$2; PASS=$3; FAIL=$4
cd $CTX
TOTAL=$(ls Dockerfile.* | wc -l)
i=0
for f in Dockerfile.*; do
  i=$((i+1))
  IID=${f#Dockerfile.}
  TAG="sweb.eval.arm64.${IID}:latest"
  if docker images -q "$TAG" | grep -q .; then
    echo "$IID skip-exists" >> $PASS; continue
  fi
  echo "[$(date +%H:%M)] ($i/$TOTAL) $IID"
  if docker build -f "$f" -t "$TAG" . > /tmp/build-current-$PREFIX.log 2>&1; then
    echo "$IID ok" >> $PASS
  else
    echo "$IID fail" >> $FAIL
  fi
done
echo "REPO-BUILD-DONE pass=$(wc -l < $PASS) fail=$(wc -l < $FAIL)"
