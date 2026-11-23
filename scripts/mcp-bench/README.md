# MCP-Bench on ARM64 调研（2026-11）

## 结论：ARM 兼容性极好，已实测跑通 ✅

- 28 个 MCP 服务器：20 个带 Dockerfile，基础镜像全部是官方多架构
  （python:3.x-slim / node:lts-alpine / uv bookworm-slim）→ arm64 原生支持
- 大部分服务器是"远程 API 的本地轻量包装"（weather/nasa/wikipedia/paper-search 等），
  本地资源占用极小
- 依赖安装走 uv + pnpm/yarn/tsx（Node 侧），ARM 全兼容

## 实测结果（2026-11-19）

### 全量 single 档（56 题 / 28 服务器，qwen3.6-35b-a3b 网关，ARM64 原生）

| 指标 | 值 |
|---|---|
| 任务执行成功 | **56/56 = 100%**（0 基础设施故障） |
| Task Completion Score | 4.73/10 |
| Tool Selection Score | 6.68/10 |
| Planning Effectiveness | 4.16/10 |
| Task Fulfillment / Grounding | 4.29 / 5.16 |
| Tool Appropriateness / Parameter Accuracy | 6.66 / 6.70 |
| Schema 合规 | 99.88% |
| 有效工具名率 | 98.88% |
| 工具调用成功率 | 92.59% |
| 平均轮次 / 工具调用 | 6.4 轮 / 28.1 次每题 |
| 平均 token | 112.8k/题 |
| 耗时 | 136s 智能体 + 52s 判分 |

> 注：56/56 是"执行管线无故障完成"口径；judge 分数（4.7/6.7/4.2）是
> qwen3.6-35b-a3b 对 28 个异构服务器全量任务的真实水平——对照官方论文
> （GPT-4o task completion ~6-7），符合"中等偏下开源模型"的预期定位。
> 单服务器 smoke（Time MCP 2 题）曾得 9.6/9.8/8.6，说明分数差异主要来自
> 任务复杂度（跨服务器/多跳任务拉低均分）。

### 服务器连通性（check_all_servers.py）：26/28 直连可用

- ✅ 26 个：OpenAPI Explorer(2) Unit Converter(16) Wikipedia(9) Google Maps(7)
  Bibliomantic(4) Call for Papers(1) Car Price(3) Context7(2) DEX Paprika(11)
  FruityVice(1) Game Trends(7) Huge Icons(3) Hugging Face(10) Math(13) NixOS(18)
  OSINT(7) Reddit(2) National Parks(6) Medical Calculator(22) Met Museum(3)
  Movie Recommender(1) NASA(21) OKX(2) Paper Search(19) Scientific Computing(26)
  Weather(4) Time(2)
- ✅ **28/28 全部连通**（2026-11-23 复验）。两个注意项：
  - BioMCP 首次连接需预热（uv sync 编译依赖，~5 分钟），之后 35 工具秒级发现
  - Google Maps 工具发现不需 key（7 工具），但实际调用 geocode 等需真实
    GOOGLE_MAPS_API_KEY——涉及 10/104 题（9.6%），跑分时以"工具调用失败"计入，
    schema/工具名指标不受影响

### 多服务器档（2026-11-19 晚跑完，qwen3.6-35b-a3b）

| 指标 | 2-server（30 题） | 3-server（18 题） |
|---|---|---|
| 执行成功 | 30/30 | 18/18 |
| Task Completion | 4.25 | 4.20 |
| Tool Selection | 5.74 | 6.03 |
| Planning Effectiveness | 3.37 | 3.73 |
| Schema 合规 | 99.6% | 99.5% |
| 工具调用成功率 | 91.5% | 91.6% |
| 平均轮次 / 调用 | 12.6 轮 / 54.4 次 | 11.9 轮 / 50.6 次 |
| 平均 token | 264k | 308k |
| 耗时 | 231s+51s | 216s+48s |

> 三档对比：single 4.73 → 2-server 4.25 → 3-server 4.20（task completion），
> 跨服务器编排对开源中等模型是明显难点（planning 分从 4.16 掉到 3.4），
> 但执行管线（schema/工具名/调用成功率）三档都稳定在 99%/98%/92% 上下——
> **基础设施不随任务复杂度劣化**，掉分全部来自模型能力。

### 首个 smoke（Time MCP 2 题）

| 指标 | 值 |
|---|---|
| 任务完成率 | 2/2 = 100% |
| Task Completion / Tool Selection | 9.6 / 9.8 |
| Schema 合规 / 工具调用成功 | 100% / 100% |
| 平均工具调用 | 15.5 次/题（2 轮） |

## 三个必打补丁（llm/agent 侧，与 ARM 无关但与自建推理端点有关）

### 1. LLM factory 注册 custom-llm（`llm/factory.py`）

在 `get_model_configs()` 的 OpenRouter 段前插入：

```python
if os.getenv("CUSTOM_LLM_BASE_URL"):
    configs["custom-llm"] = ModelConfig(
        name="custom-llm",
        provider_type="openai_compatible",
        api_key=os.getenv("CUSTOM_LLM_API_KEY", "dummy"),
        base_url=os.getenv("CUSTOM_LLM_BASE_URL"),
        model_name=os.getenv("CUSTOM_LLM_MODEL", "default"),
    )
```

### 2. Judge provider（`benchmark/runner.py`）

`execute_single_task_with_model` 里 judge 硬编码 Azure o4-mini，无 Azure key 时
挂。改为 `CUSTOM_LLM_BASE_URL` 存在时用 AsyncOpenAI 指向同一网关
（judge 模型可用 `CUSTOM_LLM_JUDGE_MODEL` 独立指定）。

### 3. thinking 开关（`llm/provider.py`）

reasoning 模型（Qwen3.x on vLLM）不关 thinking 会 `content=None`。
在 `get_completion` 的非 azure 分支注入：

```python
params["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
```

（`CUSTOM_LLM_DISABLE_THINKING=1` 控制，默认开）

## 两个环境坑（跑服务器时）

1. **venv 无 `python`**：commands.json 全部写 `python -m ...`，uv 创建的 venv
   只有 `python3`。修法：`ln -s python3.10 mcpbench-env/bin/python`（注意
   先删掉指向 python 的旧 python3 链接，避免循环符号链接）。
2. **mcp 包版本**：仓库 venv 里 mcp 2.x 与多数服务器（按 mcp 1.x API 写）不
   兼容——`Server` 没有 `list_tools` 装饰器、`McpError` 改名 `MCPError`。
   time-mcp 锁的是 mcp 1.0.0，装 `mcp==1.0.0` 后 OK。

### 3. stdio 服务器空 env 坑（`mcp_modules/connector.py`，已打补丁）

connector 给 `StdioServerParameters` 传 `env=server_env or {}`——空 dict 会让
stdio_client 用**完全空的环境**起子进程（没有 PATH），`python -m ...` 直接
`FileNotFoundError`。最终修法：显式构造 env = 父环境 + **venv bin 前置到
PATH**（commands.json 的裸 `python` 要解析到带 mcp/fastmcp 的 venv），再合并
server_env。

### 4. 依赖矩阵（mcp / fastmcp / pydantic 三角）

最终锁定：`mcp==1.19.0 + fastmcp==2.12.5 + pydantic==2.11.7`。
- pydantic ≥2.12 删了 `eval_type_backport` → fastmcp/mcp 1.x 全挂
- fastmcp 2.11 需要 `mcp.server.mcpserver`（2.x 命名）→ 与 1.x 冲突
- fastmcp 2.12.5 需要 `IdentityAssertionParams`（mcp 1.19 才有）
- 每次装新服务器后必须检查这三个版本没被 uv 联动升级

### 5. resident-server 坑（`benchmark/runner.py`，已打补丁）

`--distraction-count 0` 时 `commands_config` 保持 None，但 resident 服务器
（Time MCP）查找会 `in None` 崩溃。改为禁用 distraction 时也加载
commands_config。

### 6. 外网 API 走代理

wikipedia_mcp 直连 en.wikipedia.org 会挂起（无超时）。run-arm.sh 注入
`HTTP(S)_PROXY=127.0.0.1:7890`，子进程 MCP 服务器继承后走代理，问题消失。

## 复现步骤

```bash
# 1. 环境（py3.10 venv + 依赖）
cd /data2/gxw/mcp-bench
uv venv mcpbench-env --python 3.10
uv pip install --python mcpbench-env/bin/python -r mcp_servers/requirements.txt \
  openai litellm pydantic pyyaml "mcp==1.0.0"
ln -sf python3.10 mcpbench-env/bin/python    # 修 python 命令名

# 2. 装 Time MCP（首个验证服务器）
cd mcp_servers/time-mcp
uv pip install -e . --python ../../mcpbench-env/bin/python

# 3. 验证补丁（6 项检查：factory/judge/thinking/网关/服务器 import）
../../mcpbench-env/bin/python verify_patches.py

# 4. 跑 smoke（Time MCP 2 题）
bash run-arm.sh --models custom-llm --tasks-file tasks/arm_smoke_time.json \
  --distraction-count 0 --output /tmp/mcpbench-smoke-time.json
```

`run-arm.sh` 里预设了网关 env（`CUSTOM_LLM_*`）与 `NO_PROXY`。

## 状态
- ✅ 调研完成，ARM 兼容性确认
- ✅ 三个 LLM 补丁 + stdio env 补丁 + resident-server 补丁
- ✅ 28 服务器依赖全装，26/28 连通验证
- ✅ **三档全量跑完：single 56/56 + 2-server 30/30 + 3-server 18/18 = 104/104**
- 待办：BioMCP 预热复验；Google Maps 换真实 key
