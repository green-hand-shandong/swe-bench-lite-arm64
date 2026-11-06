# 论文/博客智能体指标复现 playbook（本机：鲲鹏 ARM64 + 16×Ascend 310P3）

> 目标：拿到一篇论文/博客里的"SWE-bench X% / Terminal-Bench Y%"指标，
> 在本机用同一数据集、同一判分逻辑复现，验证或对比。

## 0. 通用原则（先读）

1. **复现 = 三要素对齐**：数据集版本 + 智能体（含 scaffold/提示词/最大步数）+ 模型。
   论文里这三个缺一不可，缺哪个就如实记录"无法对齐"。
2. **判分我们已解决**：300 个 ARM64 镜像 + 离线 mock httpbin + 官方判分逻辑，
   与 x86 榜单同题同判分，resolved 率可直接对比。
3. **本机算力定位**：16×310P3 适合推理（vllm-ascend 已跑通 Qwen3-30B），
   不适合闭源模型复现——闭源指标只能对 API 或放弃。

## 1. 复现决策树（拿到论文先问四个问题）

```
论文用什么基准？
├─ SWE-bench (Lite/Verified/Multilingual)     → 路线 A（我们已就绪 ✅）
├─ Terminal-Bench 2.0                         → 路线 B（Harbor，需 ARM 适配）
├─ τ-bench / GAIA / BrowseComp 等工具调用类    → 路线 C（EvalScope）
└─ 私有数据集                                  → 路线 D（看数据是否公开）

论文用什么模型？
├─ 开源模型（Qwen/Llama/DeepSeek/GLM...）      → vllm-ascend 本地部署 ✅
└─ 闭源模型（Claude/GPT）                      → API key 或放弃

论文用什么智能体？
├─ 无智能体（单轮 prompt → patch）             → run_agent_eval.py 单轮模式 ✅
├─ SWE-agent / mini-swe-agent / OpenHands     → 框架装好指到我们的数据集/镜像
└─ Claude Code / Codex CLI                    → EvalScope External Agent Bridge
```

## 2. 路线 A：SWE-bench 系复现（最成熟，1~2 天）

前置（已完成 ✅）：300 ARM 镜像、修复后数据集、mock httpbin、判分管线。

```bash
# Step 1 部署被测模型（vllm-ascend，示例 Qwen3-30B）
docker run -d --name eval-model --network host \
  quay.io/ascend/vllm-ascend:v0.23.0-310p \
  --model /workspace/models/<model> --served-model-name <model> --port 8000

# Step 2a 单轮基线（管线内置）
python3 scripts/agent-eval/run_agent_eval.py \
  --api-base http://127.0.0.1:8000/v1 --model <model> \
  --run_id <paper>-repro --max_instances 0 --max_workers 4

# Step 2b 多轮智能体（论文若用 SWE-agent/mini-swe-agent）
pip install mini-swe-agent  # 100 行智能体，官方榜单标配
mini-swe-agent --dataset docs/swe-bench-lite-arm.parquet \
  --model <model> --output predictions.jsonl   # 参数以框架文档为准
python3 scripts/agent-eval/run_agent_eval.py \
  --predictions predictions.jsonl --run_id <paper>-repro --judge-only

# Step 3 对比：报告 resolved 率 vs 论文数字
```

**对齐检查清单**（写进复现记录）：
- [ ] 数据集 split 与论文一致（Lite=300 题 / Verified=500 题）
- [ ] 智能体 scaffold、system prompt、max_steps、temperature 与论文一致
- [ ] 模型版本号一致（同一 checkpoint 而非同名系列）
- [ ] 判分口径：论文报的是 resolved 还是 submitted

## 3. 路线 B：Terminal-Bench 2.0（Harbor，3~5 天）

```bash
pip install harbor
# 镜像拉取：TBD tasks 大多为 x86 镜像 → 需逐个确认 arm64 版本或源码重建
harbor run --dataset terminal-bench@2.0 --agent mini-swe-agent \
  --model openai/<model> --n-concurrent 4
```
**ARM 风险**：官方 task 镜像多为 x86。策略：优先挑 README 标注支持 arm64 的
task；x86-only 的 task 用我们 arm_convert.py 的思路重建（Ubuntu 基础 + apt 源换
ports.ubuntu.com）。预计 20% 的 task 需要手工适配。

## 4. 路线 C：τ-bench / GAIA 等工具调用类（EvalScope，2~3 天）

```bash
pip install evalscope[agent]
evalscope eval --model <model> --api-url http://127.0.0.1:8000/v1 \
  --datasets tao_bench / gaia   # 具体名以 evalscope eval --help 为准
```
优势：agent trace 全程记录可视化；昇腾生态亲和。ARM 风险低（纯 py + Docker sandbox）。

## 5. 路线 D：私有数据集
数据不公开则无法复现，只能按论文描述"尽力对齐"并在报告标注差异。

## 6. 本机资源与并发预算

| 资源 | 现状 | 测评时的用法 |
|---|---|---|
| 16×310P3 NPU | vllm-ascend 已跑通 | 被测模型推理；单模型单卡组即可，留余量 |
| 1TB 内存 | 充裕 | 判分容器并发 ≤ 4（sympy 大数计算内存敏感） |
| 磁盘 /data0 217G 空闲 | 镜像已占 ~370G | 新基准镜像预估预留 100G+ |
| 外网 | httpbin 等已 mock 离线 | pip/HF 走 TUNA 镜像 |

## 7. 交付物模板（每次复现产出）

```
repro/<paper-name>/
├── notes.md            # 三要素对齐检查清单 + 与论文的差异点
├── predictions.jsonl   # 模型原始输出
├── <run_id>.json       # 官方判分报告
└── summary.md          # 复现结论：X% vs 论文 Y%，差异归因
```

## 8. 建议的复现顺序（按性价比）

1. **Qwen3-30B 单轮 SWE-bench Lite**（1 天）——验证管线 + 拿自家基线
2. **mini-swe-agent 多轮 SWE-bench Lite**（1~2 天）——智能体加成对比
3. **EvalScope τ-bench / GAIA**（2~3 天）——扩展到工具调用类
4. **Harbor Terminal-Bench 2.0**（3~5 天）——终端类，需 ARM 适配投入
5. 按论文需求定制其余基准
