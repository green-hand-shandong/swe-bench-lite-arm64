#!/bin/bash
# MCP-Bench on ARM64 with the internal OpenAI-compatible gateway.
# Usage: bash run-arm.sh [--list-models | --models custom-llm --tasks-file <file>]
set -e
cd "$(dirname "$0")"

# --- Gateway (OpenAI-compatible) ---
export CUSTOM_LLM_BASE_URL="http://10.40.92.149:8788/v1"
export CUSTOM_LLM_API_KEY="adebf1cc83b2c455129205f8ec9885e9ec8da1d9004365ca"
export CUSTOM_LLM_MODEL="qwen3.6-35b-a3b"
# Judge defaults to the same gateway model; override with CUSTOM_LLM_JUDGE_MODEL
export CUSTOM_LLM_DISABLE_THINKING=1   # reasoning model: content=None otherwise

# --- Proxy hygiene: gateway is intranet-direct ---
export NO_PROXY="localhost,127.0.0.1,10.40.92.149"
export no_proxy="$NO_PROXY"

# --- Local venv (py3.10, requirements + openai/litellm/pydantic/pyyaml installed) ---
source "$(dirname "$0")/mcpbench-env/bin/activate"

exec python run_benchmark.py "$@"
