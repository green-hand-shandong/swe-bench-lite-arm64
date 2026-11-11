# BFCL（Berkeley Function-Calling Leaderboard）on ARM64

BFCL V4 纯 Python wheel（py3.12），ARM 原生可用。已验证：qwen3-8b（本机 310P vllm）
simple_python 类别 400 题 **Accuracy 94%**（官方榜单同类别头部水平 90-100%）。

## 安装

```bash
uv venv --python 3.12 bfcl-env
uv pip install --python bfcl-env/bin/python bfcl-eval qwen_agent soundfile
```

## 对接本地 vLLM 的 3 个补丁（bfcl-env/.../bfcl_eval/model_handler/api_inference/qwen.py）

BFCL 的 QwenAPIHandler 硬编码 dashscope 端点和 vllm 特定参数，打 3 个补丁后即可
指向任意 OpenAI 兼容端点（含本地 vllm / 内网网关）：

1. **base_url 可配置**（原硬编码 dashscope.aliyuncs.com）：
   `self.client = OpenAI(base_url=os.getenv("QWEN_BASE_URL", "http://localhost:8000/v1"), ...)`
2. **served model 名可配置**（vllm serve 的名字与 BFCL handler 名不同）：
   3 处 `'model': ...` 改为 `os.getenv("QWEN_MODEL_NAME", <原名>)`
3. **thinking 开关结构**（vllm 对 Qwen3 要求嵌套）：
   `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`
   （顶层 `enable_thinking` 无效——这是踩过最深的一个坑）

## 跑评测

```bash
export QWEN_API_KEY=dummy
export QWEN_BASE_URL=http://127.0.0.1:30000/v1     # 本地 vllm
export QWEN_MODEL_NAME=qwen3-8b                     # vllm --served-model-name
export OPENAI_API_KEY=dummy                         # BFCL 入口校验用
bfcl generate  --model qwen3-8b --test-category simple_python --num-threads 4 --allow-overwrite
bfcl evaluate --model qwen3-8b --test-category simple_python
```

## 已知注意

- FC 模式（`qwen3-8b-FC`）需要 vllm 启动参数 `--enable-auto-tool-choice --tool-call-parser hermes`
- 网关限流（429）会中断 generate 且不落盘——本地 vllm 无此问题
- 结果目录：`BFCL_PROJECT_ROOT`（默认 site-packages/bfcl_eval）下的 `result/` 与 `score/`
