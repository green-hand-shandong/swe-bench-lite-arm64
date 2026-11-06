# 智能体评测生态调研（2026-11）

本文回答两个问题：除了 SWE-bench Lite，还有哪些常见的智能体测试；以及主流
评测编排框架的选型对比。所有项目均可与我们已有的 **300 个 ARM64 镜像**配合。

## 一、常见智能体测试基准（按类型）

### 代码修复类（与 SWE-bench Lite 同类）
| 基准 | 规模/特点 | 说明 |
|---|---|---|
| **SWE-bench Lite** | 300 题 | 我们已 ARM 化 ✅ |
| **SWE-bench Verified** | 500 题，人工校验 | 官方精选子集，行业标配 |
| **SWE-bench Multilingual** | 多语言仓库 | 不止 Python，Java/Go/JS 等 |
| **SWE-bench Pro** | Scale AI 出品 | 更难、更长 horizon、低污染 |
| **SWE-bench Multimodal** | 含截图/UI | 前端类任务 |
| **Aider Polyglot** | 多语言 | Exercism 题目，测编辑能力 |
| **SWE-Gym / R2E-Gym** | 可训练环境 | 偏 RL 训练场景 |

### 终端操作类（近两年最热）
| 基准 | 说明 |
|---|---|
| **Terminal-Bench 2.0** | 真实终端任务（laude-institute 出品，Harbor 官方基准），考 shell/编译/调试 |
| **InterCode** | Bash/SQL 交互式执行 |
| **OSWorld** | 完整桌面 OS GUI 操作 |
| **WebArena / VisualWebArena** | 网页浏览器操作 |

### 工具调用/多轮类
| 基准 | 说明 |
|---|---|
| **τ-bench / τ²-bench / τ³-bench** | 客服对话 + 工具调用 + 规则校验（航空/零售/电信/银行域） |
| **GAIA** | 通用助理多跳任务（网页/文件/推理） |
| **MCP-Atlas / Toolathlon** | MCP 工具调用能力 |
| **BrowseComp / WideSearch** | 深度搜索 |
| **AutomationBench / JobBench** | 自动化办公任务 |

### 综合长程类
| 基准 | 说明 |
|---|---|
| **SWE-Lancer** | 真实 Freelancer 付费任务，按美元计价 |
| **GDPval** | 真实职业任务 |
| **ResearchRubrics** | 研究类长任务评分 |

## 二、评测编排框架选型

### Harbor（harbor-framework/harbor，⭐6.8k）— **推荐重点看**
Terminal-Bench 官方 harness，**定位与我们的用法最接近**：
- `harbor run --dataset terminal-bench@2.0 --agent claude-code --model ...` 一条命令
- 支持任意 agent 适配器（Claude Code、OpenHands、Codex CLI、mini-swe-agent...）
- 支持第三方基准（SWE-bench、Aider Polyglot 等）
- 本地 Docker 或云端沙箱（Daytona/Modal 等几百家并发）
- 还能生成 RL rollout（训练用）
- **与我们资产的关系**：它的 task 格式（task.toml + 环境 Dockerfile）与我们
  构建的 300 个 ARM 镜像同构，理论上可以写个转换器把我们的任务打包成 Harbor task

### EvalScope（modelscope/evalscope，⭐3.7k）— **魔搭官方，中文生态最好**
- 通用 LLM 评测框架，**Agent 评测模式**是亮点：内置 AgentLoop 多轮驱动 +
  Docker sandbox + 完整 agent trace 记录可视化
- 支持基准：SWE-bench Agentic、SWE-bench Multilingual、SWE-bench Pro、
  GAIA、τ³-bench、BrowseComp、BigCodeBench、Toolathlon 等
- **External Agent Bridge**：直接评 Claude Code / Codex CLI 这类现成 CLI——
  把 CLI 的 LLM 流量转发到你的评测模型，完整轨迹记录
- 已有 OpenCode / OpenHands runner
- 与阿里 vllm-ascend 生态同源，对昇腾+NPU 环境亲和（我们服务器正好是这套）

### SWE-agent / mini-swe-agent（⭐20.7k / 9.1k）— 智能体本体
- SWE-agent：Princeton 出品，SWE-bench 官方配套智能体，ACI 设计经典
- mini-swe-agent：**100 行代码**的极简智能体，官方推荐做评测的默认底座
  （SWE-bench 官方榜单大量条目用它跑）——我们接自研智能体可以参考它

### OpenHands（原 OpenDevin，⭐4w+）— 全功能智能体平台
- 浏览器/终端/代码全能力，自带 eval harness
- 事件流架构，适合做复杂多轮任务的智能体底座

### 其他值得知道的
- **SWE-rebench**：持续更新的无污染 SWE 任务源（防数据泄漏）
- **Repo2RLEnv**（HuggingFace）：把任意 repo 转成可验证 RL 环境
- **SWE-Lancer**（OpenAI）：真实付费任务，美元计价

## 三、与 SWE-Lite-ARM 的组合建议

```
当前资产：300 个 ARM64 镜像 + 修复后数据集 + mock httpbin + 判分管线
```

| 目标 | 建议路径 |
|---|---|
| 快速评自家模型（API 单轮） | 已有 `run_agent_eval.py` ✅ |
| 多轮智能体评测 | **EvalScope**（对昇腾生态最友好，trace 可视化）或 mini-swe-agent（极简可控） |
| 终端类任务扩展 | **Harbor** + Terminal-Bench 2.0（镜像构建方式与我们同构，可平移） |
| 模型训练/RL | Harbor rollout 或 Repo2RLEnv |

ARM 适配注意：Harbor/EvalScope 的云端沙箱 provider（Daytona/Modal）在 ARM 上
支持有限，本地 Docker provider 是最稳路径——正好我们的 300 镜像就是本地 Docker。
