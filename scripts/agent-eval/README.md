# 自动化测评管线

一条命令完成「模型推理 → 补丁收集 → 官方判分 → resolved 报告」。

## 快速开始

```bash
# 对接 vllm/sglang 等 OpenAI 兼容 API（本地模型服务）
python3 scripts/agent-eval/run_agent_eval.py \
  --api-base http://127.0.0.1:8000/v1 \
  --model Qwen2.5-32B-Instruct \
  --run_id qwen30b-v1 \
  --max_instances 30     # 先跑 30 题验证，0=全部

# 断点续跑：再执行同一命令即可（自动跳过已完成的题）

# 只重判分（已有预测文件）
python3 scripts/agent-eval/run_agent_eval.py \
  --predictions my.jsonl --run_id rerun --judge-only
```

## 输出

- `predictions.jsonl` — 模型原始补丁
- `<run_id>.<run_id>.json` — 官方判分报告（resolved 数）
- `logs/run_evaluation/<run_id>/` — 每题的完整判分日志

## 多模型对比

```bash
for M in "Qwen2.5-32B-Instruct" "DeepSeek-V3" "GLM-4.5"; do
  python3 scripts/agent-eval/run_agent_eval.py \
    --api-base http://127.0.0.1:8000/v1 --model $M --run_id "$M"
done
# 各模型 resolved 率横向对比
```

## 两种模式

### 单轮模式（本脚本内置）——适合"闭卷"基线评测

把 problem_statement 直接给模型，要求输出 git diff。**模型看不到仓库代码**，
patch 质量有限（弱模型可能产出无法 apply 的 diff），适合快速对比不同模型的
"盲修"能力，或验证管线连通性。

### 多轮智能体模式（推荐）——真实 SWE 能力评测

智能体在容器内的 /testbed 里反复"看代码→改代码→跑测试"，产出可 apply 的 patch。
两种接法：

1. **SWE-agent / OpenHands / mini-swe-agent 等框架**：它们原生支持 SWE-bench
   数据集。注意指定我们的 ARM 镜像（`image` 字段）与本地数据集路径。框架产出
   predictions.jsonl 后用 `--judge-only` 判分。

2. **自研循环**（run_agent_eval.py 的 run_single_turn 可扩展为多轮）：
   ```
   起容器 → 提取 bug 相关文件内容给模型 → 模型给 patch → 容器内 git apply
   → 失败则把报错回喂模型重试（最多 N 轮）→ 成功后收集 diff
   ```

判分环节两者完全一致。

## 说明

- 镜像/数据集/mock httpbin 全部复用 SWE-ARM 现有资产，判分离线可跑。
- 断点续跑：推理阶段中断后再执行同一命令，自动跳过已完成的题目。
