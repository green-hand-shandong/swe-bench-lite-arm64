# SWE-bench Lite ARM64（SWE-ARM）

在一台**鲲鹏 ARM64** 服务器（Ubuntu 20.04 / Docker / 内核 5.4）上，把 SWE-bench Lite
全部 **300 个实例**的评测镜像从 x86_64 原生化到 `linux/arm64`，并用官方
`swebench.harness.run_evaluation` 完成 golden 判分——**零基础设施改造，纯软件方案**。

| 指标 | 数值 |
|---|---|
| ARM64 镜像构建 | **300/300（100%）** |
| 官方判分可运行 | **300/300（0 error / 0 infra failure）** |
| Golden patch resolved | **279/300 = 93.0%** |

> 21 个 unresolved 均为测试环境问题（外网 httpbin 依赖、宽松 pin 后版本漂移等），
> 非 ARM 架构缺陷。逐题根因见 [`docs/swe-arm-report.md`](docs/swe-arm-report.md)。

## 为什么可以做

SWE-bench 的评测镜像是"Ubuntu 基础镜像 + conda 环境 + 源码 checkout"的纯 Python
生态，代码本身不含 x86 机器码。ARM 化的全部障碍都在**依赖获取层**：

1. 官方 Dockerfile 写死 `FROM --platform=linux/amd64` 和 x86 Miniconda 安装器
2. conda 包以三段式 pin（`pkg=version=x86_build_hash`）锁死了 x86 专有 build
3. 部分包在 aarch64 渠道根本没有对应版本（gtk4、UV-CDAT 系、老 qt/pyqt 等）
4. 个别源码构建依赖（freetype/qhull tarball）从 sourceforge/qhull.org 下载，
   构建环境内不可达
5. `pip install` 从 github 拉源码，外网不稳

这五类问题都可以用**机械化的 Dockerfile 转换 + 少量逐题甄别**解决，不需要
qemu-user 模拟（比 x86 模拟快一个数量级），也不需要重新制作数据集。

## 结果总览

| 仓库 | 题数 | 镜像构建 | golden resolved |
|---|---|---|---|
| django/django | 114 | ✅ 114/114 | ✅ 全部 |
| sympy/sympy | 77 | ✅ 77/77 | ✅ 全部 |
| matplotlib/matplotlib | 23 | ✅ 23/23 | 18/23 |
| scikit-learn/scikit-learn | 23 | ✅ 23/23 | 19/23 |
| pytest-dev/pytest | 17 | ✅ 17/17 | ✅ 全部 |
| sphinx-doc/sphinx | 16 | ✅ 16/16 | ✅ 全部 |
| astropy/astropy | 6 | ✅ 6/6 | ✅ 全部 |
| psf/requests | 6 | ✅ 6/6 | 1/6（httpbin 外网依赖） |
| pylint-dev/pylint | 6 | ✅ 6/6 | 1/6 |
| pydata/xarray | 5 | ✅ 5/5 | 3/5 |
| mwaskom/seaborn | 4 | ✅ 4/4 | ✅ 全部 |
| pallets/flask | 3 | ✅ 3/3 | ✅ 全部 |
| **合计** | **300** | **300 (100%)** | **279 (93.0%)** |

完整判分结果见 [`gold.gold-arm-full.json`](gold.gold-arm-full.json)。

## 快速开始

### 0. 前置条件

- 鲲鹏/飞腾等 aarch64 服务器，Ubuntu 20.04+，Docker 20+
- Python 3.10+（运行转换器与判分）
- 可访问清华 TUNA 镜像（conda/pypi/miniconda 均走镜像，不依赖官方源）
- `pip install swebench datasets pandas pyarrow`（判分用）

### 1. 转换 Dockerfile

```bash
# 对每个仓库执行（repo slug 见 SWE-bench 数据集 repo 字段）
python3 scripts/arm_convert.py django/django
python3 scripts/arm_convert.py sympy/sympy
# ... 12 个仓库
```

产出：
- `/tmp/arm-contexts/<repo__repo>/Dockerfile.<instance_id>` — ARM 化 Dockerfile
- `/tmp/arm-mirrors/<repo__repo>` — 本地 git 裸仓（构建内 clone，绕开外网）
- `docs/swe-bench-lite-arm.parquet` — 带 `image` 字段的数据集（判分按此找镜像）

### 2. 构建镜像

```bash
# 单仓库批量构建（跳过已存在镜像，记录 pass/fail 列表）
bash scripts/build-repo.sh /tmp/arm-contexts/django__django dja /tmp/dja-pass.txt /tmp/dja-fail.txt

# 失败列表统一重试（多轮，轮间隔 10 分钟）
bash scripts/retry-all-failed.sh
```

镜像命名：`sweb.eval.arm64.<instance_id>:latest`

### 3. 官方 golden 判分

```bash
export HF_ENDPOINT=https://hf-mirror.com

# 把 arm64 镜像 retag 成数据集 image 字段名（run_evaluation 按此找镜像）
python3 scripts/retag-arm-to-x86.py

# 官方判分（predictions=gold 即跑 golden patch 验证镜像可用性）
python3 -m swebench.harness.run_evaluation \
  --dataset_name docs/swe-bench-lite-arm.parquet \
  --predictions_path gold \
  --run_id gold-arm-full \
  --max_workers 4
```

跑模型评测时把 `--predictions_path` 换成你的模型预测 JSON 即可，流程完全一致。

## 转换器做了什么（arm_convert.py）

| # | 转换 | 说明 |
|---|---|---|
| 1 | 基础镜像平台 | `FROM --platform=linux/amd64` → `linux/arm64` |
| 2 | Miniconda 安装器 | x86 官方源 → TUNA aarch64 镜像 |
| 3 | conda 频道 | environment.yml 内嵌 channels → TUNA main/free/conda-forge + nodefaults |
| 4 | build string 松绑 | `pkg=ver=x86hash` 三段式 → `pkg=ver`，让求解器自选 aarch64 build |
| 5 | pip 源 | 统一注入 TUNA pypi 镜像 |
| 6 | git clone | github URL → 本地裸仓（COPY 注入构建上下文） |
| 7 | 新鲜度守卫删除 | 移除官方 Dockerfile 里的 commit 计数守卫（mirror 场景失效） |

### 逐题甄别（无法机械转换的部分）

不同仓库的"硬骨头"不同，全部记录在
[`docs/swe-arm-adaptation-log.md`](docs/swe-arm-adaptation-log.md)，典型几类：

- **aarch64 渠道缺包**：gtk4=4.14.1、libuuid=2.38.1、glib 链、libgfortran4/_openmp_mutex
  llvm 变体、openssl 1.0.2（py3.7）、qt/pyqt 5.9.x、icu/libxml2、UV-CDAT 系（cdms2 等）
  → 能松绑的松绑，纯 x86 的从环境删除
- **源码构建依赖预置**：老版本 matplotlib 的 setup.py 会现场下载
  freetype-2.6.1 / qhull tarball（sourceforge/qhull.org 不可达）→ 预下载源码树，
  COPY 注入到源码 `build/` 目录（注意：setupext 检查的是**目录**，只放 tgz 无效）
- **set -u 与 conda activate**：`qt-main_activate.sh` 的未绑定变量在 `set -euxo pipefail`
  下会杀死构建 → 在 `conda activate testbed` 前注入 QT 环境变量守卫
- **老 setup.py backend**：pylint 老版本无 `build_editable` hook →
  `pip install -e . --no-build-isolation`（`--no-use-pep517` 需要新 pip，老 pip 反而不识别）
- **markupsafe==1.0 与新 setuptools**：`cannot import name 'Feature'` →
  markupsafe 升 1.1.1 + conda 区 `setuptools=57.*`

## 复现判分结果

判分结果文件 [`gold.gold-arm-full.json`](gold.gold-arm-full.json)：
`resolved 279 / completed 300 / error 0 / infra_failure 0`。

21 个 unresolved 的分仓分布与根因（httpbin 外网依赖、宽松 pin 后版本漂移等）
见 [`docs/swe-arm-report.md`](docs/swe-arm-report.md)。

## 目录结构

```
swe-bench-lite-arm64/
├── scripts/
│   ├── arm_convert.py         Dockerfile ARM 化转换器（核心）
│   ├── build-repo.sh          单仓库批量构建
│   ├── retry-all-failed.sh    失败列表多轮重试调度
│   ├── fix-env-missing.py     conda 环境自动求解与缺包松绑工具
│   └── retag-arm-to-x86.py    镜像 retag（官方判分兼容）
├── docs/
│   ├── swe-arm-report.md           总报告（判分结果与根因分析）
│   ├── swe-arm-adaptation-log.md   逐题适配记录与踩坑（最有价值）
│   ├── swe-arm-plan.md             方案设计
│   └── swe-bench-lite-arm.parquet  带 image 字段的数据集（300 实例）
├── gold.gold-arm-full.json         官方判分结果
└── README.md
```

## 文档

- [`docs/swe-arm-report.md`](docs/swe-arm-report.md) — 总报告：判分结果、unresolved 根因分析
- [`docs/swe-arm-adaptation-log.md`](docs/swe-arm-adaptation-log.md) — 逐题适配决策、踩坑与修复（最详细）
- [`docs/swe-arm-plan.md`](docs/swe-arm-plan.md) — 立项时的可行性分析与方案设计

## License

MIT
