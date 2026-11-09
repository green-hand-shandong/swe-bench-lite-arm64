# Terminal-Bench 2.0 ARM 化报告（2026-11-08）

## 结果

| 状态 | 数量 |
|---|---|
| ARM64 镜像构建成功 | **88 / 89（98.9%）** |
| 外网不可达待重试 | 1（install-windows-3.11，win311.img） |

## 转换方法（tb2-arm-convert.py，与 SWE-bench arm_convert 同思路）

1. **apt 源 → TUNA**（debian/ubuntu 双格式）
2. **pip → TUNA**（幂等注入）
3. 基础镜像全为多架构官方镜像（python/ubuntu/debian），无需更换
4. 显式 x86 引用仅 2 个 QEMU 任务（下载 x86 alpine ISO，属任务语义）

## 成功构建 78 个任务

覆盖：python 工具链、编译类（cython/pov-ray/compcert）、系统管理
（git-webserver/nginx/openssl）、数据处理、密码学、LaTeX、视频处理等。

## 逐题适配记录（原 11 个未完成任务 → 9 个已解决）

| 任务 | 问题 | 适配方案 | 结果 |
|---|---|---|---|
| train-fasttext | HF yelp 数据集下载 | hf-mirror 预下载 + COPY | ✅ |
| query-optimize | HF oewn.sqlite | 同上 | ✅ |
| bn-fit-modify | github raw csv | hf-mirror 预下载 + COPY | ✅ |
| crack-7z-hash | github john.git clone | 本地 mirror clone | ✅ |
| reshard-c4-data | HF c4 数据集 | Dockerfile 注入 HF_ENDPOINT=hf-mirror | ✅ |
| financial-document-processor | uv 下载 python-build-standalone | UV_PYTHON_INSTALL_MIRROR=ghproxy | ✅ |
| qemu-alpine-ssh / qemu-startup | bullseye-security 404（bullseye EOL） | archive.debian.org | ✅ |
| mteb-retrieve | pytrec-eval-terrier sdist 联网构建 | 预构建 aarch64 wheel + COPY | ✅ |
| install-windows-3.11 | archive.org win311.img 下载挂起 | Dockerfile 已改 COPY，待文件 | ⏳ |
| fix-git | 引用的 github repo 404 | setup.sh 改为直接构造 git 历史（判分只对比文件哈希，内容来源无关） | ✅ |

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
