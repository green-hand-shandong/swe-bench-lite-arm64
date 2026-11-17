# τ-bench on ARM64（多轮工具调用 + pass^k 一致性）

## 安装（零 ARM 障碍，全纯 Python）
```bash
git clone https://github.com/sierra-research/tau-bench
uv venv --python 3.12 taubench-env
uv pip install --python taubench-env/bin/python -e tau-bench
```

## 运行（agent 与 user 模拟器都用 OpenAI 兼容端点）
```bash
export OPENAI_API_KEY=<key>
export OPENAI_BASE_URL=http://<endpoint>/v1   # 本地 vllm 或内网网关
python run.py --env retail \
  --model openai/qwen3-8b --model-provider openai \
  --user-model openai/qwen3-8b --user-model-provider openai \
  --num-trials 1 --start-index 0 --end-index 1
```

## 踩坑记录
1. **results/ 目录**：run.py 写 checkpoint 前不建目录，首次运行会 FileNotFoundError
   → `mkdir -p results/<agent-strategy>-<model>-<temp>_range_<s>-<e>_user-<usermodel>` 或给 run.py 加 makedirs
2. **vllm 后端必须开 tool parser**：tool-calling 策略发 `tool_choice="auto"`，
   vllm 报 "auto tool choice requires --enable-auto-tool-choice and --tool-call-parser"
   → vllm serve 加 `--enable-auto-tool-choice --tool-call-parser hermes`（Qwen3 用 hermes）
3. **Qwen3 思考模式**：vllm 关闭 thinking 的正确姿势是
   `extra_body: {"chat_template_kwargs": {"enable_thinking": false}}`（顶层 enable_thinking 无效）
4. **镜像 NPU 初始化**：vllm-ascend v0.23 镜像的 torch_npu autoload 偶发
   "Failed to load backend extension"——宿主驱动升级后与旧镜像 CANN 不匹配。
   nemotron 用的 v0.30 镜像（CANN 9.2）兼容当前驱动；旧 w8a8 权重需配旧版 mindie/vllm-ascend
5. **用户模拟器**：默认 gpt-4o，本地化时 agent/user 都指向同一 OpenAI 兼容端点即可

## 状态
- 管线打通：对话循环、工具调用、判分逻辑全部就绪（AgentSetupTimeout/ckpt 路径均已修）
- 未出分：本机 Qwen3-8B 权重目录被外部清理（/data1/models/Qwen3-8B 空了），
  w8a8 变体与当前 vllm-ascend 镜像不兼容；网关当时也在故障窗口
- 恢复路径：网关恢复后直接跑（管线无改动），或重新下载 BF16 权重用 v0.30 镜像
