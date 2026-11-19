# MCP-Bench on ARM64 调研（2026-11）

## 结论：ARM 兼容性极好，已实测跑通 ✅

- 28 个 MCP 服务器：20 个带 Dockerfile，基础镜像全部是官方多架构
  （python:3.x-slim / node:lts-alpine / uv bookworm-slim）→ arm64 原生支持
- 大部分服务器是"远程 API 的本地轻量包装"（weather/nasa/wikipedia/paper-search 等），
  本地资源占用极小
- 依赖安装走 uv + pnpm/yarn/tsx（Node 侧），ARM 全兼容

## 实测结果（2026-11-19，首个任务跑通）

**Time MCP 单服务器 2 题（arm_smoke_time.json），qwen3.6-35b-a3b（网关），ARM64 原生：**

| 指标 | 值 |
|---|---|
| 任务完成率 | 2/2 = 100% |
| Task Completion Score | 9.6/10 |
| Tool Selection Score | 9.8/10 |
| Planning Effectiveness | 8.59/10 |
| Schema 合规 / 工具名有效 / 调用成功 | 100% / 100% / 100% |
| 平均工具调用 | 15.5 次/题（2 轮） |
| 耗时 | 76s 智能体 + 45s 判分 |
| token | 16.5k/题 |

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
`FileNotFoundError`。改成 `env=server_env if server_env else None`，让
`get_default_environment()`（继承 PATH/HOME 等）生效。

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
- ✅ 三个 LLM 补丁 + stdio env 补丁，6/6 验证通过
- ✅ 首个任务跑通（Time MCP 2 题，100%）
- 待办：其余 26 个服务器逐个装依赖（Node 侧需 install.sh 实测）→
  全量 28 服务器任务（single/2-server/3-server 三档）
