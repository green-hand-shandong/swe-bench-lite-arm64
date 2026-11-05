#!/bin/bash
# 对所有仓库的 fail 列表统一重试（最多 3 轮，轮间隔 10 分钟）
for ROUND in 1 2 3; do
  echo "=== retry round $ROUND $(date +%H:%M) ==="
  for PF in /tmp/mpl-fail.txt /tmp/mpl2-fail.txt /tmp/skl-fail.txt /tmp/pyt-fail.txt /tmp/sph-fail.txt /tmp/ast-fail.txt /tmp/req-fail.txt /tmp/ast2-fail.txt /tmp/xar-fail.txt /tmp/sea-fail.txt /tmp/fla-fail.txt; do
    [ -f "$PF" ] || continue
    CTXBASE=$(basename $PF | cut -d- -f1)
    case "$PF" in
      *mpl*) CTX=/tmp/arm-contexts/matplotlib__matplotlib;;
      *skl*) CTX=/tmp/arm-contexts/scikit-learn__scikit-learn;;
      *pyt*) CTX=/tmp/arm-contexts/pytest-dev__pytest;;
      *sph*) CTX=/tmp/arm-contexts/sphinx-doc__sphinx;;
      *ast2*) CTX=/tmp/arm-contexts/pylint-dev__pylint;;
      *ast*) CTX=/tmp/arm-contexts/astropy__astropy;;
      *req*) CTX=/tmp/arm-contexts/psf__requests;;
      *xar*) CTX=/tmp/arm-contexts/pydata__xarray;;
      *sea*) CTX=/tmp/arm-contexts/mwaskom__seaborn;;
      *fla*) CTX=/tmp/arm-contexts/pallets__flask;;
    esac
    NEWFAIL="$PF.retry$ROUND"
    > "$NEWFAIL"
    while IFS= read -r line; do
      IID=$(echo "$line" | cut -d' ' -f1)
      STATE=$(echo "$line" | awk '{print $2}')
      [ "$STATE" = "skip-exists" ] && continue
      TAG="sweb.eval.arm64.$IID"
      if docker images -q "$TAG" | grep -q .; then echo "$IID ok" >> "$NEWFAIL"; continue; fi
      echo "[$(date +%H:%M)] R$ROUND building $IID"
      if docker build -f "$CTX/Dockerfile.$IID" -t "$TAG" "$CTX" > "/tmp/retry-$IID.log" 2>&1; then
        echo "$IID ok" >> "$NEWFAIL"
      else
        echo "$IID fail" >> "$NEWFAIL"
      fi
    done < "$PF"
    # 覆盖原 fail 列表为新的
    cp "$NEWFAIL" "$PF"
  done
  REMAIN=0
  for PF in /tmp/*-fail.txt; do grep -c fail "$PF" 2>/dev/null; done | paste -sd+ | bc 2>/dev/null
  FAILSUM=$(cat /tmp/*-fail.txt 2>/dev/null | grep -c fail)
  echo "round $ROUND done, remaining fails: $FAILSUM"
  [ "$FAILSUM" = "0" ] && break
  sleep 600
done
echo "RETRY-ALL-DONE"
