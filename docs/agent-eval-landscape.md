# 智能体评测生态调研（2026-11）

本文回答三个问题：除了 SWE-bench Lite，还有哪些常见的智能体测试；**论文里报什么
指标**；以及主流评测编排框架的选型对比。所有项目均可与我们已有的 **300 个 ARM64
镜像**配合。

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

## 二、常见指标（论文里报什么数）

> 依据：SWE-agent 论文（arXiv 2405.15793）、GAIA（2311.12983）、
> τ-bench（2406.12045）、BALROG（2411.13543）、Agent 综述（2503.16416）。

### 核心三件套（几乎所有论文都报）

| 指标 | 定义 | 用在哪 |
|---|---|---|
| **Resolve Rate / Success Rate** | 全部测试通过的比例（SWE-bench 口径） | SWE-bench 系、代码修复类的**主指标** |
| **Accuracy** | 答案正确的比例（准精确匹配） | GAIA、问答/工具调用类的主指标 |
| **Cost** | 平均推理成本（$/实例 或 token 数） | SWE-agent 起成为标配（论文设 $4/实例 预算上限） |

### 扩展指标（不同基准的特色口径）

| 指标 | 定义 | 出处 |
|---|---|---|
| **pass@1 / pass@k** | k 次尝试至少一次成功（代码生成口径） | SWE-agent Fig.4（6 次跑 Lite 测方差） |
| **pass^k（pass hat k）** | k 次独立尝试**全部**成功的概率，测**一致性** | τ-bench 提出：gpt-4o pass¹ 61% 但 pass⁸ <25% |
| **% Resolved（pass@1 口径）** | SWE-bench 主指标的标准叫法 | SWE-agent 论文主指标 |
| **Average Progress / Achievement %** | 0~100 归一化进度分（按成就比例） | BALROG（游戏环境统一分） |
| **Efficiency / Time to Answer** | 平均耗时（分钟/题） | GAIA Table 4（人类 L1 6.8min vs L3 17.7min） |
| **Tool call correctness** | 工具选择 + 参数 + 执行输出的逐步正确性 | τ-bench 规则奖励（r_action × r_output） |
| **Step-level progress** | 每步是否推进用户目标 | Galileo action advancement |
| **Milestone completion** | 关键导航节点完成率 | WebCanvas |
| **Trajectory 统计** | 无效/幻觉动作的记录统计 | BALROG |
| **Difficulty 分层** | 按 Level 1/2/3 分层报告 | GAIA（L1 无工具 ≤5 步 / L2 5~10 步 / L3 任意） |

### 论文报告惯例（复现时对齐口径用）

- **SWE-bench 系**：主指标 `% Resolved`，配 `Avg Cost`；常规补充分析是按
  repo / issue 年份分层（SWE-agent Table 6-7）；对比基线是 BM25 检索 + 直接生成补丁
- **τ-bench**：主指标 `pass¹`，配 `pass^k`（一致性）；规则奖励 = 终态数据库
  精确匹配 × 回复包含必要信息（如 "54.04"）
- **GAIA**：主指标 `accuracy`，配分层（L1/L2/L3）+ 时间；300/466 题答案
  不公开供榜单用，固定答案格式 `FINAL ANSWER: ...`
- **成本口径**：SWE-agent 用"已解决实例的平均成本"且设 $4/实例预算上限——
  复现时注意论文报的是"全实例平均"还是"已解决实例平均"
- **2025 综述指出的缺口**：成本/效率（token 用量、API 开销、推理时长）跟踪不足，
  新论文越来越多把成本与 resolve rate 并列报告

## 三、评测编排框架选型

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

## 四、与 SWE-Lite-ARM 的组合建议

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
