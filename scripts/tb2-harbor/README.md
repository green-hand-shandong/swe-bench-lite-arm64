# Terminal-Bench 2.0 × Harbor 官方 harness（ARM64）

用 Harbor 官方框架跑我们 ARM 化的 89 个 TB2 任务，替换之前自建脚本的方式。
跑通验证：`adaptive-rejection-sampler` 任务，mini-swe-agent + qwen3.6-35b-a3b（网关），
trial completed=1 errored=0，官方 verifier 出 reward。

## 前置

1. py3.12 + Harbor（纯 py wheel，ARM 原生可用）：
   ```bash
   uv venv --python 3.12 harbor-env
   uv pip install --python harbor-env/bin/python harbor
   ```
2. `docker compose` 插件（Harbor 用 `docker compose` 子命令）：
   ```bash
   mkdir -p /usr/local/lib/docker/cli-plugins
   ln -sf /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
   ```
3. 下载官方数据集：
   ```bash
   harbor download terminal-bench@2.0 -o /data2/gxw/tb2-harbor
   ```
4. **agent-ready 镜像**：官方任务镜像 amd64-only，用我们 ARM 化的 `tb2-arm64/<task>:latest`
   做底，预装 uv + mini-swe-agent（避免 agent setup 阶段从 astral.sh/github 下载超时）：
   ```dockerfile
   FROM tb2-arm64/<task>:latest
   RUN apt-get update && apt-get install -y curl git python3-pip \
       && pip3 install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple uv \
       && UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
          UV_PYTHON_INSTALL_MIRROR=https://ghproxy.net/https://github.com/astral-sh/python-build-standalone/releases/download \
          uv python install 3.12 \
       && UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
          uv tool install --python 3.12 mini-swe-agent --with litellm --with orjson --with fastapi
   ENV OPENAI_API_KEY=... \
       OPENAI_BASE_URL=http://10.40.93.109:8788/v1 \
       MSWEA_CONFIGURED=1 \
       MSWEA_COST_TRACKING=ignore_errors
   ```
   注意 ENV 层是必须的——`--env-file` 的变量只进 compose PID1，不进 agent 的 docker exec。

## 跑一个任务

```bash
cp -r /data2/gxw/tb2-harbor/terminal-bench/<task> /data2/gxw/harbor-local-tasks/
sed -i "s|docker_image = .*|docker_image = \"tb2-arm64/<task>:mswea-final\"|" \
  /data2/gxw/harbor-local-tasks/<task>/task.toml
bash run.sh <task>
```

## mini-swe-agent 配置要点（mswea-textbased.yaml）

| 配置 | 值 | 原因 |
|---|---|---|
| `model.model_class` | `litellm_textbased` | 默认 LitellmModel 是 tool-calls 风格，文本模型永远无动作 |
| `model.model_kwargs.base_url` | 网关地址 | base_url 放 config 顶层无效（pydantic 无此字段），必须进 model_kwargs |
| `model.model_kwargs.max_tokens` | 4000 | 太小会 finish_reason=length 截断 → RepeatedFormatError |
| system/instance 模板前缀 | `/no_think` | 网关 reasoning 模型 content=None → 无动作 |
| model_name | `openai/qwen3.6-35b-a3b` | 必须带 provider 前缀，否则 litellm 报 provider 缺失 |
| `MSWEA_CONFIGURED=1` | env | 跳过首次交互式向导 |
| `MSWEA_COST_TRACKING=ignore_errors` | env | 自定义模型不在 litellm 价格表 |
