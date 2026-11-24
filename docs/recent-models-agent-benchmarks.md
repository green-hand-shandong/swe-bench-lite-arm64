# 近期主流模型的智能体基准使用调研（2026-11-24，SearXNG 检索版）

> 检索：本机 SearXNG（google cse 引擎）；一手来源：GLM-5/5.2、Kimi-K3、
> DeepSeek-V3.2、Qwen3.5 官方 README/HF card；Qwen3-Coder、MiniMax-M1 次之。

## 一、2026 年最新的模型表都在测什么

| 基准 | GLM-5.2 | Kimi K3 | DeepSeek-V3.2 | Qwen3.5-397B | MiniMax-M1 |
|---|---|---|---|---|---|
| **Terminal-Bench 2.x**（2.0/2.1） | ✅ 81.0 | ✅ 88.3 | ✅ 37.7(V1) | ✅ 52.5 | — |
| **SWE-bench Verified** | — | — | ✅ 67.8 | ✅ | ✅ |
| **FrontierSWE**（超长 horizon） | ✅ | ✅ 81.2 | — | — | — |
| **SWE-Marathon**（超长 horizon） | ✅ | ✅ 42.0 | — | — | — |
| **DeepSWE v1.1** | ✅ | ✅ 67.5 | — | — | — |
| **PostTrainBench** | ✅ | ✅ 36.6 | — | — | — |
| **MCPMark(-Verified)** | — | ✅ 94.5 | — | ✅ | — |
| **OSWorld-Verified** | — | ✅ 84.8 | — | ✅ | — |
| **OSWorld 2.0** | — | ✅ | — | — | — |
| **AndroidWorld** | — | — | — | ✅ | — |
| **τ²-bench** | ✅ | ✅ | — | ✅ 87.1/91.6 | ✅ |
| **BrowseComp(+zh)** | ✅ | ✅ | ✅ 40.1 | ✅ | — |
| **BFCL-V4** | — | — | — | ✅ | — |
| SWE-bench Multilingual | ✅ 66.7 | — | ✅ 57.9 | ✅ | — |
| LiveCodeBench v6 | — | — | ✅ 74.1 | ✅ | ✅ |
| HLE(-Verified) | ✅ 42.8 | ✅ | ✅ 19.8 | ✅ | — |
| GDPval-AA v2 | — | ✅ | — | — | — |

（GLM-4.7 一代表另含 SWE-bench Verified 73.8 / Terminal-Bench Hard / τ²-Bench /
BrowseComp；Kimi K2.6 亦为多模态 agentic 表。）

## 二、2026 趋势（对比 2025 的变化）

1. **Terminal-Bench 2.1 取代 2.0 成为终端标配**（Harbor 框架，官方持续更新）
2. **超长 horizon 编码三件套兴起**：FrontierSWE（20 小时级）、SWE-Marathon、
   DeepSWE v1.1——GLM-5.2/Kimi K3 的主打差异化
3. **MCPMark-Verified** 成为 MCP 工具调用新标杆（Nota-NetsPresso，
   5 环境：Notion/GitHub/Filesystem/PostgreSQL/Playwright）
4. **OSWorld-Verified / OSWorld 2.0**：GUI 方向升级为 verified 版（xlang-ai 官方）
5. τ²-bench、BrowseComp、SWE-bench Verified 保持不变，仍是常青树
6. GDPval-AA（OpenAI 真实职业任务）、AndroidWorld（移动端）开始进入模型表

## 三、对照我们的 ARM 化覆盖与行动项

| 基准 | 我们状态 | 行动 |
|---|---|---|
| Terminal-Bench 2.0 | ✅ 89/89 | **升级到 2.1**（Harbor 数据集直接换 tag，判分兼容，成本低） |
| SWE-bench Verified | ⚠️ 有 Lite 300/500 | **补 200 题镜像**（所有模型表的标配口径） |
| SWE-bench Multilingual | ❌ | 多语言镜像，成本高，缓 |
| τ²-bench | ✅ retail 81.7% | **补 airline/telecom 域**（≈0 成本，纯 API） |
| BrowseComp | ❌ | 纯检索+judge，需稳定搜索后端（可用本机 SearXNG！） |
| MCPMark | ❌（有 MCP-Bench 28/28） | **值得做**：5 环境（Notion/GitHub/Filesystem/Postgres/Playwright）中 4 个可自托管，与 MCP-Bench 互补 |
| OSWorld-Verified / 2.0 | ✅ OSWorld 368 题 | **升级 verified 判分集**（我们的 QEMU provider 直接复用） |
| AndroidWorld | ❌ | 需 Android 模拟器（ARM 上 KVM 跑 aarch64 镜像可行，成本中） |
| FrontierSWE / SWE-Marathon / DeepSWE | ❌ | 超长 horizon（20h 级）任务，判分依赖官方私有 harness，暂缓 |
| PostTrainBench / GDPval / HLE | ❌ | 非环境类或私有，暂缓 |
| Aider-Polyglot / LiveCodeBench | ❌ | 纯 Python 沙箱，成本低，可作补充 |

## 四、推荐 ARM 化路线（按 2026 模型表出现频率 × 成本）

1. **Terminal-Bench 2.1**（Harbor `--dataset terminal-bench@2.1`，我们 89 题的
   2.0 经验直接复用；新任务数更多但构建方法一致）
2. **τ²-bench airline + telecom**（0 成本）
3. **SWE-bench Verified 剩余 200 题**（复用 arm_convert.py 流水线）
4. **MCPMark**（4/5 环境可自托管；Notion 需真实账号，可先跑 GitHub/Postgres/Filesystem/Playwright）
5. **OSWorld-Verified**（复用 QEMU provider，重跑判分集）
6. BrowseComp（用本机 SearXNG 做搜索后端，恰好今天已把 searxng 配好出网）
