# 最新旗舰模型的智能体基准调研（2026-11-24，SearXNG 检索 v3）

> 覆盖用户指定系列：**Qwen4-Max、GLM-5.4/5.3、GPT-6.2 Astra、Claude Fable 5.2、
> DeepSeek V4.1/V4-Flash**。一手来源：Anthropic 官方页、DeepSeek-V4-Flash HF card、
> qwen.ai/yottalabs Qwen4-Max、GLM-5.3 docs、Harbor Hub、Sierra tau-bench repo。

## 一、各旗舰模型的智能体基准表

### Claude Fable 5.2（Anthropic，2026-11-09）
- **FrontierSWE v2** 69.9%、**FrontierCode 2.0** 49.1%、**Terminal-Bench-Science 0.1** 74.6%
- **OSWorld 2.1**（offline set, partial）**89.3%**（对 Opus 5.5 83.5%）
- AutomationBench 51.4%、CVE Rediscovery 89.6%、AA-Briefcase v1.1 66.1%
- 定位语："demanding reasoning and long-horizon agentic work"

### GPT-6.2 Astra（OpenAI，2026-11 中）
- **Agents' Last Exam**（33 模型榜第一）：多步职业工作流
- **Terminal-Bench-Science 64.6%**、DeepSWE v1.1 74.1%（AA 榜第一）
- APEX 67.2%；AA Coding Agent Index v2.1 组成 = FrontierCode-AA 2.0 +
  Terminal-Bench 4.1 + SWE-Atlas-QnA-AA

### Qwen4-Max（阿里，2026-11-15，1M ctx）
- **Terminal-Bench 4.0** 48.5（vs 上代 38.9）、**DeepSWE v1.1** 75.7
- **Agents' Last Exam** 46.7（上代 27.9）、HLAB-Vals
- 官方 16 基准图：agentic coding 75.7 vs 69.3（Qwen3.8-Max）
- 开源计划：小尺寸 Qwen4 权重待发布（当前 Max 为 API）

### GLM-5.4 / 5.3（智谱，5.4 刚发布 ~1 天）
- **GLM-5.4**（Looped Transformer 新架构，内置视觉）：**未发布官方基准表**
  （社区/媒体确认"missing coding benchmark scores"）
- **GLM-5.3**：Terminal-Bench **3.0** 28.3（上代 4.6）、Terminal-Bench 2.1 66.9、
  Z.ai Code Bench +50%、CyberGym SOTA
- GLM-5.2 基线：Terminal-Bench 2.1 81.0/82.7、FrontierSWE、SWE-Marathon

### DeepSeek V4.1 / V4-Flash（2026-09+，HF card 官方表）
| 基准 | V4-Flash | V4-Pro |
|---|---|---|
| Terminal Bench 2.0 | 65.4~75.1 | 67.9 |
| SWE Verified | 73.7~80.8 | 80.6 |
| SWE Pro | 49.1~58.6 | 55.4 |
| SWE Multilingual | 69.7~77.5 | 76.2 |
| **BrowseComp** | 53.5~85.9 | 83.4 |
| **MCPAtlas** Public | 64.0~74.2 | 73.6 |
| **Toolathlon** | 40.7~54.6 | 51.8 |
| HLE w/ tools | 40.3~54.0 | 48.2 |
| GDPval-AA (Elo) | 1314~1674 | 1554 |

## 二、2026-11 基准生态快照（对比上月调研的增量）

| 基准 | 版本演进 | 自托管可行性 |
|---|---|---|
| Terminal-Bench | 2.1 → **3.0 → 4.0 → 4.1**（连续基准，Harbor Hub 标签化） | ✅ Harbor 数据集直接换 tag；4.0 起校准任务资源（时间/CPU/内存） |
| τ-bench | τ² → **τ³**（新增 **banking 域** + voice 模态 + airline/retail 修复） | ✅ 同一 repo（sierra-research/tau-bench），≈0 成本 |
| OSWorld | 2.0 → **2.1**（108 长 horizon 任务，offline 子集 82 题） | ✅ xlang-ai 官方，QEMU 路线可复用 |
| MCP 工具调用 | MCPMark → **MCPAtlas**（Scale AI：36 真实 MCP 服务器/220 工具）、**Toolathlon**（ICLR 2026，503 任务/25 MCP 服务器，**完全自托管**） | ✅ Toolathlon 自包含最友好；MCP-Atlas 需跑真实 MCP 服务器 |
| 超长 horizon | FrontierSWE v2、FrontierCode 2.0、SWE-Atlas-QnA（AA 指标 v2.1 三件套） | ❌ 私有 harness / 官方判分 |
| 新形态 | Agents' Last Exam（36 最难工作流）、AutomationBench、Terminal-Bench-Science、Vending-Bench 3、GDPval-AA | 混合（ALE 部分可自托管） |

## 三、ARM 化行动清单（按旗舰模型表出现频率 × 成本，2026-11-24 修订）

| 优先级 | 基准 | 出现在谁的表 | ARM 成本 |
|---|---|---|---|
| **1** | **τ³-bench banking + voice**（τ² repo 已升级） | Kimi/MiniMax/Qwen3.5/GLM | ≈0（纯 API，repo 更新即可） |
| **2** | **Terminal-Bench 4.0/4.1**（Harbor tag 切换） | Qwen4-Max/DeepSeek/GLM-5.3/Mistral | 低（我们 2.0 的 89 题构建经验直接复用；任务资源校准需重新过一遍） |
| **3** | **Toolathlon**（503 任务/25 MCP 服务器，自包含） | DeepSeek V4 官方表 | 中（Docker 自托管，与 MCP-Bench 经验互补） |
| **4** | **OSWorld 2.1**（108 任务，offline 82 子集） | Fable 5.2/Kimi Qwen | 中（QEMU provider 复用；2.1 的长 horizon 任务需重建 VM 快照） |
| **5** | **MCPAtlas**（Scale AI） | DeepSeek V4 官方表 | 中（36 真实 MCP 服务器，部分需账号） |
| **6** | **SWE-bench Verified 剩余 200 题** | DeepSeek/Qwen/全行业 | 中（arm_convert 流水线复用） |
| 7 | Agents' Last Exam（可自托管部分） | GPT-6.2/Qwen4-Max | 中-高 |
| 8 | BrowseComp | DeepSeek/GLM/Qwen | 环境≈0（**本机 SearXNG 即搜索后端**），判分需 LLM judge |
| 9 | FrontierSWE v2 / FrontierCode / SWE-Atlas | Fable 5.2/GPT-6.2/Kimi | ❌ 私有，暂缓 |
| 10 | SWE-bench Multilingual | DeepSeek/GLM/Qwen | 高（多语言镜像），缓 |

## 四、结论

2026-11 的旗舰表收敛于：**Terminal-Bench 4.x + τ³（banking）+ MCPAtlas/Toolathlon +
OSWorld 2.1 + BrowseComp** 这五类。我们已有的资产（TB 2.0 89 题、τ² retail 81.7%、
MCP-Bench 28/28、OSWorld 368 题 QEMU、SearXNG）覆盖了全部五类的"旧版本"，
升级路径都在现有管线内。最优先执行：τ³ banking（0 成本）→ Terminal-Bench 4.x
（Harbor tag 切换）→ Toolathlon（自包含新基准）。
