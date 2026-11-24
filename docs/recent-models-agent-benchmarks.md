# 近期主流模型的智能体基准使用调研（2026-11-24）

> 依据各官方 README/HF card 一手信息：GLM-4.7（zai-org）、DeepSeek-V3.2-Exp、
> Kimi K2（MoonshotAI）、MiniMax-M1、Qwen3-Coder（blog）。

## 一、各家报告的智能体基准汇总

| 基准 | GLM-4.7 | DeepSeek-V3.2 | Kimi K2 | MiniMax-M1 | Qwen3-Coder |
|---|---|---|---|---|---|
| SWE-bench Verified | ✅ 73.8 | ✅ 67.8 | ✅ 65.8~71.6 | ✅ 55.6~72.5 | ✅ 67.8/69.6 |
| SWE-bench Multilingual | ✅ 66.7 | ✅ 57.9 | ✅ 47.3 | — | — |
| Terminal-Bench 2.0 | ✅ 41.0 | ✅ 37.7 | ✅（TB） | — | — |
| τ²-bench（retail/airline/telecom） | ✅ | — | ✅ 三域全测 | ✅ airline+retail | — |
| BrowseComp | ✅ | ✅ 40.1 + zh | — | — | — |
| Aider-Polyglot | — | ✅ 74.5 | ✅ | — | — |
| LiveCodeBench | — | ✅ 74.1 | ✅ v6 | ✅ | ✅ |
| HLE（Humanity's Last Exam） | ✅ 42.8 | ✅ 19.8 | — | — | — |
| BFCL | — | — | — | — | —（Qwen 系统内测） |

**结论：智能体基准的"四大金刚"是 SWE-bench Verified、Terminal-Bench 2.0、
τ²-bench、BrowseComp；辅助是 Aider-Polyglot / LiveCodeBench / SWE-bench Multilingual。**

## 二、对照我们的 ARM 化覆盖

| 基准 | 主流模型在测 | 我们 ARM 状态 | 出分能力 |
|---|---|---|---|
| SWE-bench Lite | （Verified 的子集） | ✅ 300/300 镜像 | ✅ 官方判分 100% |
| SWE-bench Verified | 全部在测 | ⚠️ 未建（500 题，是 Lite 的超集） | 需新增 200 题镜像 |
| SWE-bench Multilingual | GLM/DeepSeek/Kimi | ❌ 未建 | 多语言镜像工程量大 |
| Terminal-Bench 2.0 | GLM/DeepSeek/Kimi | ✅ 89/89 镜像 | ✅ Harbor 管线通 |
| τ-bench retail | MiniMax/Kimi | ✅（纯 API 无 ARM 障碍） | ✅ 81.7% |
| τ²-bench airline/telecom | Kimi（telecom 新域） | ✅ 纯 API | ✅ 可直接跑 |
| BrowseComp | GLM/DeepSeek | ❌ 纯检索+API（无环境依赖） | ✅ 可直接跑（需联网 judge） |
| Aider-Polyglot | DeepSeek/Kimi | ⚠️ 225 题 Exercism，x86 容器 | 可 ARM 化（轻量） |
| LiveCodeBench | DeepSeek/Kimi/MiniMax | ⚠️ 纯 Python 沙箱 | ✅ 可直接跑 |
| OSWorld | （较少上官方表） | ✅ 368 题 100% | ✅ 双模型基线 |
| WebArena | （少见于最新表） | ✅ 4/5 站 | ✅ 8 题基线 |
| MCP-Bench | （2025 新基准） | ✅ 28/28 | ✅ 104 题 |
| BFCL | Qwen 系内部 | ✅ simple_python 94% | ✅ |

## 三、ARM 化优先级建议（按"模型表上出现频率 × ARM 化成本"排序）

1. **τ²-bench telecom/airline 域**（成本≈0：纯 API + 工具模拟器）
   - Kimi K2 三个域都测、MiniMax 测两域——补齐后 τ² 全域可对齐
2. **LiveCodeBench**（成本低：纯 Python 执行沙箱，无 x86 依赖）
   - DeepSeek/Kimi/MiniMax 都报；RL 训练侧也常用
3. **Aider-Polyglot**（成本低：225 题 Exercism + 官方 benchmark harness，Python 为主）
   - DeepSeek/Kimi 都报；与 SWE-bench 互补（编辑能力）
4. **SWE-bench Verified**（成本中：500 题里 Lite 已覆盖 300，需新增 200 题镜像）
   - **所有模型都报它**——行业标配，补齐后我们可与任何模型表直接对齐
5. **BrowseComp**（成本≈0 环境，但需要联网搜索后端 + 判分 LLM）
   - GLM/DeepSeek 报；依赖搜索 API 的可用性
6. SWE-bench Multilingual（成本高：Java/Go/JS/C 多语言镜像）
   - GLM/DeepSeek/Kimi 报；放最后
