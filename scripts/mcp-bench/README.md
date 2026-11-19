# MCP-Bench on ARM64 调研（2026-11）

## 结论：ARM 兼容性极好，可直接跑

- 28 个 MCP 服务器：20 个带 Dockerfile，基础镜像全部是官方多架构
  （python:3.x-slim / node:lts-alpine / uv bookworm-slim）→ arm64 原生支持
- 大部分服务器是"远程 API 的本地轻量包装"（weather/nasa/wikipedia/paper-search 等），
  本地资源占用极小
- 依赖安装走 uv + pnpm/yarn/tsx（Node 侧），ARM 全兼容

## LLM 接入（qwen3.6-35b-a3b）

`llm/factory.py` 的 `create_llm_provider` 已内置 `openai_compatible` provider
（api_key + base_url），只需在 `get_model_configs()` 增加一段 env 驱动的自定义配置：

```python
if os.getenv("CUSTOM_LLM_BASE_URL"):
    configs["custom-llm"] = ModelConfig(
        name="custom-llm",
        provider_type="openai_compatible",
        api_key=os.getenv("CUSTOM_LLM_API_KEY"),
        base_url=os.getenv("CUSTOM_LLM_BASE_URL"),
        model_name=os.getenv("CUSTOM_LLM_MODEL"),
    )
```

（小 patch，待环境准备就绪后提交）

## 安装

```bash
conda/uv create python=3.10
cd mcp_servers && bash ./install.sh   # 装 uv/pnpm/yarn/tsx + 各服务器依赖
```

## 状态
- 调研完成，ARM 兼容性确认
- 待办：install.sh 实测 → LLM factory patch → 首个任务跑通
