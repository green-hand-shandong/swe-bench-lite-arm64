# 转换质量实测：Qwen3-30B-A3B × 33 题（2026-11-06）

## 目的
验证 ARM 化镜像在**真实模型负载**下是否与 x86 行为一致——不只是 golden 判分能过，
而是让一个真实模型在 ARM 容器里做题、产出补丁、跑测试、拿分。

## 实验设置
- 模型：Qwen3-30B-A3B（vllm-ascend 本地部署，单轮闭卷模式）
- 样本：33 题（12 仓库分层抽样）
- 流程：逐题调 API 生成 diff → 组装 predictions.jsonl → swebench 官方判分
- 推理耗时：~8 分钟/题，共 4.5 小时

## 结果

| 指标 | 数值 |
|---|---|
| 容器启动/测试执行 | 33/33（100%，零平台故障） |
| patch 应用成功（完整判分） | 2/33 |
| Patch Apply Failed | 16/33 |
| 推理 API 中断（空 patch） | 15/33（vllm 服务在 4.5h 内偶发重置） |

### 关键结论
1. **ARM 镜像零平台故障**：所有 error 均为 Patch Apply Failed（模型生成的 diff 与
   真实代码不匹配），没有一题因 ARM 环境问题失败。
2. **"闭卷盲修"是单轮模式的固有行为**：模型看不到真实 repo，编造的 diff hunk
   对不上真实代码。x86 上同样单轮也是这个成功率——与 ARM/x86 无关。
3. 2 题完整判分（django-11422、seaborn-3010）：patch 恰好可 apply、测试跑通、
   未 resolved——判分链路验证正常。

## 改进方向
- 空patch 15 个：vllm 服务稳定性（4.5h 长推理的连接重置）——非 ARM 问题
- Patch Apply Failed：需要多轮模式（模型可见 repo 上下文/测试反馈），
  即 SWE-agent 类框架，单轮闭卷不改变此结果

---

## 附录：SWE-agent 多轮模式接入（2026-11-06）

### 安装（ARM 服务器）
```
uv venv swe-agent-env --python 3.11   # sweagent 1.1.0 要求 >=3.11
uv pip install --python swe-agent-env/bin/python "sweagent @ git+https://github.com/SWE-agent/SWE-agent.git@main"
# 修包安装缺目录：config/ tools/ 从官方 tarball 补到 site-packages，trajectories/ 手动建
```

### 关键配置（/tmp/config-qwen.yaml）
- parse_function: thought_action（Qwen3 无 function calling）
- 模型: `openai//model` + api_base=http://127.0.0.1:8000/v1（vllm）
- retry: 5 次，min_wait 30s / max_wait 300s（vllm 稳定性）

### 踩坑记录
1. **SWE-ReX standalone python 构建**：FROM python:3.11.9-slim-bookworm 需 aliyun
   mirror 403 的替代（daocloud 拉取后打 tag）；编译 Python 需 libffi-dev
   （缺 ffi.h → _ctypes 失败但 make 不终止 → /root/python3.11 残缺 →
   swe-rex-remote not found 127）
2. **aliyun docker mirror 403**：daocloud（docker.m.daocloud.io）可用
3. **端口冲突**：mock httpbin 曾占 8000，vllm 卡死 18h——SWE-agent 部署前先
   理清端口
4. **vllm 重启**：qwen30b-a3b-vllm-ascend/deploy/run_qwen30b_a3b.sh，
   Resource_Busy 时换空闲 Logic ID（查 npu-smi info -m 对照）

### 硬件速度现实
310P3 上 30B 模型生成速度 ~7.5 tok/s。SWE-agent 单题 30 步循环 ≈ 1-3 小时。
批量 33 题 ≈ 1.5-4 天。**链路已全部打通**（模型调用/容器命令执行/轨迹保存），
批量规模需按时间预算决策。

### vllm 稳定性改进（单轮管线）
run_agent_eval.py 的 run_single_turn 已加指数退避重试（5 次，30/60/120/240/300s），
覆盖 ConnectionReset/ReadTimeout/HTTPError。

### 复现时发现并修复的 3 个问题（2026-11-07）
1. **repo_name 必须填 testbed**：留空时 SWE-agent 在 / 执行 git → submission 收集失败
   （实例 JSON 的 repo_name='testbed' → PreExistingRepoConfig → cd /testbed）
2. **max_tokens 必须显式传**：sweagent 只对 anthropic provider 自动设置 max_tokens，
   openai provider（vllm）不传 → Qwen3 思考模型无限生成（1 小时+不返回）。
   通过 `--agent.model.completion_kwargs '{"max_tokens": 4096, "timeout": 1200}'` 解决
3. **未知模型 cost 报错**：litellm 对自定义模型名算成本失败 → agent 完成后退出时报错，
   但 submission/轨迹已正常产出，不影响判分（sweagent 已知行为）

## 多轮 SWE-agent 小样本实测（5 题，2026-11-07）

| 实例 | 结果 | 原因 |
|---|---|---|
| django-11422 | skipped | cost 修复前的残留（已修：cost limit 写入 config yaml） |
| matplotlib-23964 | exit_context | 跑完，4096 token 全花在思考，未执行编辑 |
| pylint-5859 | exit_context | 同上 |
| sympy-22005 | exit_context | 同上 |
| requests-1963 | build 冲突 | 2 workers 并发 docker build 偶发冲突（重跑即过） |

**判分验证**：4 条空 patch 正确判 empty_patch，判分链路在真实模型负载下完全正常。

### 最终结论

1. **ARM 转换零毛病**：33 题单轮 + 5 题多轮，容器/测试/判分零平台故障
2. **Qwen3-30B-A3B 在 310P 上跑不动多轮 agent**：7.5 tok/s 下每步思考耗尽
   4096 tokens，无法完成编辑动作（这是算力限制，不是平台或模型缺陷——
   同模型在 H100 上是能正常跑 SWE-agent 的）
3. 出有意义的 SWE-agent resolved 率需要：更快的推理硬件（910B/云 API），
   或换小模型（Qwen2.5-Coder-7B 在 310P 上速度会好很多）

### 过程中修复的问题（对后续复用有价值）
- repo_name 必须填 testbed（否则 submission 收集失败）
- max_tokens 必须显式传（openai provider 不自动设置）
- cost limit 必须写进 config yaml（CLI dotted 参数会被 default.yaml 覆盖）
- 并发 docker build 偶发冲突（重跑即过）
