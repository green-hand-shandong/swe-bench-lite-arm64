# SWE-ARM：鲲鹏 ARM64 上的 SWE-bench 评测环境计划

> 目标：在 ARM64 服务器（鲲鹏 / Ubuntu 20.04 / Docker 29）上重建 SWE-bench
> 评测环境，形成"同一基准 × ARM 原生执行"的完整跑分能力，并与芯合沙箱平台
> 的评测编排打通。

## 一、调研结论（2026-11-02 实测核实）

1. **官方 harness 原生支持 ARM**：`swebench/image_builder/image_spec.py`
   中 `ImageSpec.arch` 明确支持 `"arm64"`（映射 `linux/arm64/v8`，镜像名
   `sweb.eval.arm64.<instance_id>`）。ARM 化只需要把数据集/构建流程的
   `arch` 默认值从 `amd64` 切到 `arm64`，属于官方预留路径，不是 hack。
2. **harness 依赖无架构绑定**：Python ≥3.10 + docker-py + datasets +
   ghapi 等，本机环境满足（Python 3.10.12 / Docker 29）。
3. **数据集可达**：`hf-mirror.com` 可拉取 `SWE-bench/SWE-bench_Lite`
   （300 题，parquet 格式）；官方 huggingface.co 被墙，需设
   `HF_ENDPOINT=https://hf-mirror.com`。
4. **Docker 构建在 ARM 上原生执行**：本机已验证多架构镜像拉取
   （python/node/maven 镜像均 aarch64 版），instance 镜像在本机 build
   即为 arm64 原生，无需 qemu 模拟（性能无损失）。
5. **长尾风险**：个别仓库的依赖 wheel 可能无 aarch64 预编译版，需源码
   编译；目标仓库初选以纯 Python 为主规避。

## 二、范围与数据集

- **数据集**：SWE-bench Lite（300 题），子集化优先跑通。
- **目标仓库初选**（纯 Python、aarch64 wheel 生态好）：
  sympy、django（已知 aarch64 CI 成熟）；后续再扩 astropy 等含 C 扩展仓库。
- **不做**：多机分布式跑分、x86 对比跑分（需要 x86 机器时另立项）、
  多模型 agent 评测（先把环境和 harness 打通）。

## 三、分阶段计划

### Phase 1：数据集 + harness 本地化（半天）
1. `pip install swebench`（源码安装 /tmp/swe-bench 或 pip 镜像源）。
2. `HF_ENDPOINT=https://hf-mirror.com` 拉取 SWE-bench_Lite 到本地
   parquet 缓存。
3. harness 跑通 `--run_id arm-smoke` 单实例验证（选 sympy 最简单题）。

**验收**：harness 能列出 instance 并生成 ARM Dockerfile。

**Phase 1 实际完成记录（2026-11-02）**：
- harness 源码安装通过（/tmp/swe-bench，含 unidiff 依赖）
- SWE-bench_Lite 300 题经 hf-mirror 全量本地化
  （docs/swe-bench-lite-arm.parquet），仓库分布：sympy 77 / matplotlib 23 /
  scikit-learn 23 / pytest 17 / sphinx 16 / 其他 144
- 官方 image 列固定 x86_64 → ARM 路线确认为本地重建（image_spec 原生支持
  arch="arm64"，镜像名 sweb.eval.arm64.<instance_id>）
- aarch64 依赖链验证：python:3.9-slim（daocloud 拉取原生 arm64）✓、
  miniconda aarch64 安装脚本（清华镜像）✓、sympy 仓库 clone ✓
- 注意：sympy instance 官方镜像名形如
  swebench/sweb.eval.x86_64.sympy_1776_sympy-11400，重建后命名走
  sweb.eval.arm64.<instance_id>

### Phase 2：ARM instance 镜像重建（1-2 天，主要是构建时间）
1. `ImageSpec.arch="arm64"` 批量生成 Dockerfile 并 build
   （本机原生构建，无 qemu）。
2. 记录每个 instance 的构建成功率与失败原因（预计 sympy 全过，
   C 扩展仓库部分需源码编译）。
3. 失败的 instance 标记 `infra_failure`，不阻塞主流程。

**验收**：≥ sympy 子集的 instance 镜像全部构建成功。

### Phase 3：接入沙箱平台评测编排（1 天）
1. 把 harness 评测流程包成芯合平台的评测任务（复用 eval_runner 的
   批量创建→执行→归档→回收编排；沙箱直接用已构建的 ARM instance 镜像）。
2. 产物归档：测试报告 + 日志入平台审计/快照体系。

**验收**：跑通 1 个 instance 的"模型补丁 → 沙箱执行 → 判分 → 归档"全链路。

### Phase 4：基线跑分报告（半天）
1. 空 agent（无补丁）基线 + 一个脚本 agent（如逐条提交 golden patch）
   验证判分正确性。
2. 产出 `docs/swe-arm-report.md`：成功率、耗时、失败分类，注明 ARM 原生。

**验收**：报告 + 平台可复现跑分入口。

## 四、风险与对策

| 风险 | 对策 |
|------|------|
| aarch64 wheel 缺失导致镜像构建失败 | 初选纯 Python 仓库；失败的标记 infra_failure 不阻塞 |
| GitHub clone 限速（instance checkout 多） | git 镜像前缀 / 失败重试；本地已通 clone |
| 数据集字段版本差异（harness 与 Lite 版本） | 用官方配套版本，lock uv.lock 中的 datasets 版本 |
| Docker 磁盘（镜像 300 个 × ~2GB） | /data2 剩余 42G+，按子集分批构建，及时 remove 中间镜像 |
| 内核 5.4 偏老 | 已实测 runsc/bwrap 均可跑；如遇新内核特性需求再升级系统 |

## 五、里程碑

- M1（Phase 1 完成）：harness ARM 冒烟通过
- M2（Phase 2 完成）：sympy 子集镜像全绿
- M3（Phase 3 完成）：平台编排全链路通
- M4（Phase 4 完成）：基线报告产出
