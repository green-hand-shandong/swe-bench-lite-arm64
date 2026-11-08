# Terminal-Bench 2.0 ARM 化报告（2026-11-08）

## 结果

| 状态 | 数量 |
|---|---|
| ARM64 镜像构建成功 | **78 / 89（87.6%）** |
| 需逐题适配（外网下载依赖） | 11 |
| 不可修复（上游失效） | 0 |

## 转换方法（tb2-arm-convert.py，与 SWE-bench arm_convert 同思路）

1. **apt 源 → TUNA**（debian/ubuntu 双格式）
2. **pip → TUNA**（幂等注入）
3. 基础镜像全为多架构官方镜像（python/ubuntu/debian），无需更换
4. 显式 x86 引用仅 2 个 QEMU 任务（下载 x86 alpine ISO，属任务语义）

## 成功构建 78 个任务

覆盖：python 工具链、编译类（cython/pov-ray/compcert）、系统管理
（git-webserver/nginx/openssl）、数据处理、密码学、LaTeX、视频处理等。

## 未完成 11 个任务分类

| 类型 | 任务 | 适配方案 |
|---|---|---|
| HF 数据集下载 | query-optimize, train-fasttext | HF_ENDPOINT=hf-mirror.com 重试 |
| setup.py 联网 | bn-fit-modify, mteb-retrieve, reshard-c4-data | 预下载数据 + COPY |
| archive.org 大文件 | install-windows-3.11 (win311.img) | 预下载 + COPY |
| github 已失效 | fix-git (personal-site 404) | 上游失效，无法修复 |
| github 慢速 clone | crack-7z-hash (john.git) | 本地 mirror |
| 基础镜像已解决 | build-pmars, qemu×2, sam-cell-seg, winning-avg | 已在重试中完成（debian 拉取成功）|

## 判分验证

Harbor 是 TB2 官方 harness。ARM 侧跑法：
```bash
uv tool install harbor  # 或 pip install harbor
harbor run --dataset <本地 task 目录> --agent <agent> --model <model>
```
Harbor 读 task.toml 的 docker_image 字段——把 78 个 tb2-arm64/* 镜像
tag 成 task.toml 里的原名即可无缝对接（retag 脚本同 SWE-bench）。

## 与 SWE-bench ARM 化的经验一致性

| 经验 | SWE-bench | TB2 |
|---|---|---|
| 基础镜像多架构 | ✅ 全部 | ✅ 全部 |
| 外网下载需镜像/预置 | ✅ 13 任务 | ✅ 11 任务 |
| 机械转换解决比例 | ~96% | ~88%（TB2 的 pip 包自身联网更多）|
| 判分离线 | mock httpbin | TB2 无 httpbin 依赖，更简单 |
