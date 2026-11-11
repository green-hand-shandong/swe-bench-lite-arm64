#!/bin/bash
# Terminal-Bench 2.0 via official Harbor harness on ARM64
# Prereqs: py3.12 venv with harbor, docker compose plugin shim, our tb2-arm64/* images
# Usage: run.sh <task-name> [model]
set -e
TASK=${1:?task name required}
MODEL=${2:-openai/qwen3.6-35b-a3b}
TASK_DIR=/data2/gxw/harbor-local-tasks/$TASK
[ -d "$TASK_DIR" ] || { echo "copy task from /data2/gxw/tb2-harbor/terminal-bench/$TASK first"; exit 1; }
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
export MSWEA_API_KEY=${MSWEA_API_KEY:-}
export HARBOR_ENV_DIR=/data2/gxw/harbor-env
cd /data2/gxw
$HARBOR_ENV_DIR/bin/harbor run \
  -p "$TASK_DIR" \
  -a mini-swe-agent \
  -m "$MODEL" \
  --ak "config_file=/data2/gxw/mswea-textbased.yaml" \
  --env-file /data2/gxw/harbor-agent.env
