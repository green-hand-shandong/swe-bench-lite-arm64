# 模型与智能体 SWE 测试指南（ARM64）

ARM 镜像就绪后，对**任意模型/智能体**跑 SWE-bench Lite 的流程完全等于官方 x86 流程：
智能体产出补丁 → 判分系统验证。判分只认一个东西：**预测文件**。

## 预测文件格式（JSONL，每行一条）

```json
{"instance_id": "django__django-10914", "model_patch": "diff --git ...", "model_name_or_path": "your-model-v1"}
```

- `instance_id`：题目 ID（300 题列表见 `docs/swe-bench-lite-arm.parquet`）
- `model_patch`：智能体产出的 git diff（模型生成的补丁）
- `model_name_or_path`：模型/智能体名字（报告里用于区分）

## 判分

```bash
export HF_ENDPOINT=https://hf-mirror.com

# 启动 mock httpbin（requests 子集需要，详见 README）
python3 scripts/mock-httpbin/mock_httpbin.py 8000 &
python3 scripts/mock-httpbin/mock_httpbin.py 443 --tls &
python3 scripts/mock-httpbin/mock_httpbin.py 80 &

python3 -m swebench.harness.run_evaluation \
  --dataset_name docs/swe-bench-lite-arm.parquet \
  --predictions_path predictions.jsonl \
  --run_id my-model-v1 \
  --max_workers 4
```

结果在 `my-model-v1.my-model-v1.json`：`resolved_instances` 即解题数。

## 智能体怎么接

判分系统**不关心补丁怎么来的**——它只吃预测文件。所以任何智能体框架都能接：

```
┌─────────────┐     problem_statement      ┌──────────────┐
│ 本数据集      │ ──────────────────────────→ │ 任意智能体     │
│ 300 题       │   （题目描述 + repo 环境）    │ (CLI/框架)    │
└─────────────┘                             └──────┬───────┘
                                                   │ 智能体在 /testbed 里改代码
                                                   ▼
                                            git diff → model_patch
                                                   │
                                                   ▼
                                     ┌────────────────────────────┐
                                     │ swebench.harness            │
                                     │ run_evaluation（ARM 镜像）   │
                                     └────────────────────────────┘
```

**给智能体的环境**：每个实例的镜像里 `/testbed` 是 checkout 好的待修仓库、
`testbed` conda 环境已配好、测试依赖齐全。智能体要做的就是在 `/testbed` 里
复现 bug、修改代码、产出 `git diff`。

两种接法：

### A. 直接跑 CLI 智能体（最快）

智能体（OpenCode / Claude Code / Aider 等）逐题启动：

```bash
# 1. 起容器（题目环境）
docker run -d --name agent-run \
  -v /data/repos/django__django-10914:/testbed \
  sweb.eval.arm64.django__django-10914 sleep infinity

# 2. 把题目描述喂给智能体，让它在 /testbed 里干活
#    （problem_statement 在 parquet 的 problem_statement 列）
# 3. 收补丁
docker exec agent-run git -C /testbed diff > patches/django__django-10914.patch
```

### B. 用 SWE-agent / OpenHands 等框架

这些框架原生支持 SWE-bench 数据集。把 `--dataset_name` 指向我们的 parquet，
框架会自己起容器跑智能体循环，产出的 predictions 文件直接送判分。

## 与 x86 基线的关系

- 同一套 SWE-bench Lite 题目、同一套判分逻辑，只是镜像换成了 ARM64 原生构建
- 298/300 与 x86 官方一致；sympy 2 题受 aarch64 libm 浮点 ULP 差异影响
  （高并发偶发，单跑稳定）
- 你的模型在 ARM 上的 resolved 率可以直接与公开的 x86 榜单对比（同题同判分）
