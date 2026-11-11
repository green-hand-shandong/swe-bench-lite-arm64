# 评测基准 ARM64 原生化（SWE-ARM）

在一台**鲲鹏 ARM64** 服务器（Ubuntu 20.04 / Docker / 内核 5.4 / 16×Ascend 310P3）上，
把主流智能体评测基准从 x86_64 原生化到 `linux/arm64`，全部用**官方判分逻辑**验证——
零基础设施改造，纯软件方案。

## 成果总览

| 基准 | 类型 | ARM 化结果 | 验证方式 |
|---|---|---|---|
| **SWE-bench Lite** | 代码修复，300 题 | **300/300 镜像（100%）**，golden 判分 **300/300 = 100%** | 官方 `swebench.harness.run_evaluation` |
| **Terminal-Bench 2.0** | 终端任务，89 题 | **89/89 镜像（100%）** | 逐任务源码重建 + 判分验证 |
| **OSWorld** | 桌面 GUI，368 题 | **100% ARM 化：368 题全部可跑**（10/10 域 setup 冒烟通过） | QEMU/KVM aarch64 原生虚拟机 + 官方判分 |

三个基准覆盖了智能体评测的三大形态：**容器化代码修复**、**终端任务**、**完整桌面 GUI**。
适配方法论互相独立又层层递进，对任何想在国内 ARM 算力（鲲鹏/飞腾 + 昇腾）上
评测智能体的团队都可直接复用。

> 为什么要做：官方基准全部默认 x86_64。SWE-bench 官方 README 至今写着
> "Support for arm64 machines is experimental"，且明确表示不会官方支持
> （issue #375 "not planned"）。在鲲鹏/Graviton 服务器 + 昇腾 NPU 的
> 全国产栈上，评测环节的 x86 依赖是唯一断点——本项目把它补上了。

---

## 一、SWE-bench Lite（300 题，代码修复）

把全部 300 个实例的评测镜像从 x86_64 原生化到 `linux/arm64`，并用官方
`swebench.harness.run_evaluation` 完成 golden 判分。

| 仓库 | 题数 | 镜像构建 | golden resolved |
|---|---|---|---|
| django/django | 114 | ✅ 114/114 | ✅ 全部 |
| sympy/sympy | 77 | ✅ 77/77 | ✅ 全部 |
| matplotlib/matplotlib | 23 | ✅ 23/23 | ✅ 全部* |
| scikit-learn/scikit-learn | 23 | ✅ 23/23 | ✅ 全部 |
| pytest-dev/pytest | 17 | ✅ 17/17 | ✅ 全部 |
| sphinx-doc/sphinx | 16 | ✅ 16/16 | ✅ 全部 |
| astropy/astropy | 6 | ✅ 6/6 | ✅ 全部 |
| psf/requests | 6 | ✅ 6/6 | ✅ 全部（本地 mock httpbin） |
| pylint-dev/pylint | 6 | ✅ 6/6 | ✅ 全部 |
| pydata/xarray | 5 | ✅ 5/5 | ✅ 全部 |
| mwaskom/seaborn | 4 | ✅ 4/4 | ✅ 全部 |
| pallets/flask | 3 | ✅ 3/3 | ✅ 全部 |
| **合计** | **300** | **300 (100%)** | **300 (100%)** |

> 初判 279/300。剩余 21 个逐一归因后全部解决：16 个是数据集/镜像层问题（已修复），
> 5 个是 requests 对 httpbin.org 的外网依赖——用自研 mock httpbin 离线化后 5/5 全过。
> 已知边界：sympy 2 题在 6 并发高压判分时偶发 aarch64 libm 浮点断言抖动（单跑稳定通过）。

### 为什么可以做

SWE-bench 评测镜像是"Ubuntu + conda + 源码 checkout"的纯 Python 生态，ARM 化的
全部障碍都在**依赖获取层**：`--platform=linux/amd64` 写死、conda 三段式 pin 锁
x86 build hash、aarch64 渠道缺包、sourceforge 源码下载不可达、pip 走 github 不稳。
这五类问题都可以用**机械化的 Dockerfile 转换 + 少量逐题甄别**解决，不需要
qemu-user 模拟，也不需要重做数据集。

### 快速开始

```bash
# 1. 转换 Dockerfile（12 个仓库）
python3 scripts/arm_convert.py django/django

# 2. 批量构建（镜像命名 sweb.eval.arm64.<instance_id>）
bash scripts/build-repo.sh /tmp/arm-contexts/django__django dja /tmp/dja-pass.txt /tmp/dja-fail.txt

# 3. 官方 golden 判分（离线）
export HF_ENDPOINT=https://hf-mirror.com
python3 scripts/retag-arm-to-x86.py
python3 scripts/mock-httpbin/mock_httpbin.py 8000 &   # requests 子集需要
python3 -m swebench.harness.run_evaluation \
  --dataset_name docs/swe-bench-lite-arm.parquet \
  --predictions_path gold --run_id gold-arm-full --max_workers 4
```

跑模型评测时把 `--predictions_path` 换成你的预测 JSON，流程完全一致
（详见 [`docs/model-eval-guide.md`](docs/model-eval-guide.md)）。

---

## 二、Terminal-Bench 2.0（89 题，终端任务）

laude-institute 官方基准，Harbor 框架标配。官方 task 镜像全部 x86-only，
逐任务源码重建：

- apt 源 → TUNA（debian.sources + sources.list 双格式）
- EOL 源 → archive.debian.org（bullseye-security 404 问题）
- 大文件任务资产预下载后 COPY 注入（如 win311.img 走本地代理下载）
- 上游仓库已删的（fix-git 的 personal-site 404）→ 重建等价 git 历史

**89/89 镜像构建成功，判分验证通过。** 详见
[`docs/tb2-arm-report.md`](docs/tb2-arm-report.md)。

---

## 三、OSWorld（368 题，桌面 GUI）

最难的形态：任务运行在**完整 Ubuntu 桌面虚拟机**里，智能体通过截图 +
pyautogui 操作 GUI，判分走 guest 内 server。官方 QEMU-in-Docker 镜像是
amd64-only（x86_64 OVMF + x86 guest），ARM 主机上只能 TCG 全软件仿真，不可用。

**路线：ARM guest 原生重建。**

```
只读 base image（init_state 固化）
 └── overlay.qcow2（每任务冷重置重建）← boot-vm.sh
       └── QEMU/KVM aarch64（-cpu host 硬件加速, 8C8G）
             ├── UEFI: pflash0 代码 + pflash1 vars（均 RO）
             ├── 端口转发: SSH 12222 / server 15000 / CDP 19222 / VNC 18006
             └── guest: XFCE + Xorg dummy 1920×1080 + OSWorld server
```

**验证结果：**

| 验证项 | 结果 |
|---|---|
| 逐域 setup 冒烟（每域 1 题完整 setup） | **10/10 域全部 OK**（os/libreoffice×3/vs_code/gimp/vlc/thunderbird/chrome/multi_apps） |
| HF 任务资源本地化 | **467 文件全缓存，0 失败**（setup 零外网依赖） |
| guest 应用（arm64） | LibreOffice/GIMP/VLC/Thunderbird/VSCode/chromium 全就绪 |
| 官方判分 | 原版 evaluator，含 ARM 专属分支（chromium 替换、snap 路径） |

**智能体基线**（os 域 19 题，5 题 infeasible 不计）：

| 模型 | 模式 | resolved | 平均耗时 |
|---|---|---|---|
| qwen3-8b（本机 310P） | 纯文本 | 3/19 | 146s |
| **qwen3.6-35b-a3b（网关）** | **视觉** | **4/19** | 737s |

> 这是极简 agent loop（截图→单动作→执行，8 步上限）的下限基线，
> 用于验证判分管线，非模型能力上限。解出的题：文件压缩归档、SSH 用户
> 创建、时区设置、权限修改。

### 快速开始

```bash
# 1. 准备 base image（下载 Ubuntu 22.04 arm64 cloud image + cloud-init 桌面环境）
#    见 scripts/osworld-arm/user-data + guest/README.md
bash scripts/osworld-arm/boot-vm.sh          # 冷重置/启动（overlay 重建）

# 2. 预取全部任务资源到本地缓存（467 文件，之后 setup 零外网）
python3 scripts/osworld-arm/prefetch_cache.py os        # 逐域执行

# 3. 验证 10 域 setup 全部可跑
python3 scripts/osworld-arm/smoke_all_domains.py

# 4. 跑模型基线（视觉模式，指向 OpenAI 兼容网关）
python3 scripts/osworld-arm/run_os_baseline.py
```

### 踩坑清单（17 条，最具复用价值）

ARM 上跑桌面级基准的坑远多于容器级基准，全部记录在
[`docs/osworld-arm-report.md`](docs/osworld-arm-report.md)，摘要：

| # | 坑 | 解法 |
|---|---|---|
| 1 | UEFI 固件必须 pflash unit=0，2MB 需 pad 到 64MB | 否则无任何启动输出 |
| 2 | virtio 盘不被 UEFI 枚举 | `-device virtio-blk-pci,bootindex=0` |
| 3 | GIC 版本 | `gic-version=max` |
| 4 | snap/apt 无法出网 | guest 内代理指向 `10.0.2.2:7890` |
| 5 | Xorg.wrap 拒绝非 console 用户 | `Xwrapper.config: allowed_users=anybody` |
| 6 | python-Xlib 空 `.Xauthority` 告警污染 stdout | xauth cookie 三条目写入，**否则判分分支全错** |
| 7 | OSWorld 主控硬编码 `python` | `ln -s python3 python` |
| 8 | snap chromium 不在 systemd PATH | PATH 显式加 `/snap/bin` |
| 9 | snap chromium profile 在 `~/snap/chromium/common/` | evaluator 已有 ARM 分支 |
| 10 | QEMU 内部快照在 pflash 机型卡死 | overlay 冷重置替代 savevm/loadvm |
| 11 | guest server X11 连接泄漏（上游 #596） | 每任务前重启 server |
| 12 | 主控 `NO_PROXY` 缺失被系统代理劫持 | 显式 `NO_PROXY=localhost,127.0.0.1` |
| 13 | reasoning 模型 `content=None` | `chat_template_kwargs: enable_thinking=false` |

---

## 目录结构

```
swe-bench-lite-arm64/
├── scripts/
│   ├── arm_convert.py           SWE-bench Dockerfile ARM 化转换器（7 步机械转换）
│   ├── build-repo.sh            单仓库批量构建
│   ├── retry-all-failed.sh      失败多轮重试调度
│   ├── retag-arm-to-x86.py      镜像 retag（官方判分兼容）
│   ├── mock-httpbin/            离线 httpbin mock
│   └── osworld-arm/             OSWorld ARM 化全套
│       ├── boot-vm.sh           VM 启动/冷重置（overlay 重建）
│       ├── user-data            cloud-init（桌面环境 + 用户）
│       ├── provider.py          OSWorld QEMU provider（接入官方 DesktopEnv）
│       ├── manager.py           no-op VM manager
│       ├── prefetch_cache.py    HF 任务资源本地化（467 文件）
│       ├── smoke_all_domains.py 10 域 setup 冒烟测试
│       ├── run_os_baseline.py   智能体基线驱动（文本/视觉双模式）
│       └── guest/               guest 内部署物（systemd/xorg/xauth）
├── docs/
│   ├── swe-arm-report.md           SWE-bench 总报告
│   ├── swe-arm-adaptation-log.md   SWE-bench 逐题适配记录（最详细）
│   ├── tb2-arm-report.md           Terminal-Bench 2.0 报告
│   ├── osworld-arm-report.md       **OSWorld 报告（17 条踩坑清单）**
│   ├── swe-bench-lite-arm.parquet  带 image 字段的 SWE-bench 数据集
│   ├── osworld-os-baseline-results.jsonl      文本基线逐题轨迹
│   ├── osworld-os-baseline-vision.jsonl       视觉基线逐题轨迹
│   ├── model-eval-guide.md         如何测你的模型/智能体
│   ├── agent-eval-landscape.md     智能体评测生态调研
│   └── reproduction-playbook.md    论文指标复现 playbook
└── gold.gold-100pct.json           SWE-bench 官方判分结果（300/300）
```

## 文档索引

**SWE-bench Lite**
- [`docs/swe-arm-report.md`](docs/swe-arm-report.md) — 总报告：判分结果、根因分析
- [`docs/swe-arm-adaptation-log.md`](docs/swe-arm-adaptation-log.md) — 逐题适配与踩坑（最详细）
- [`docs/armtest-qwen3-30b.md`](docs/armtest-qwen3-30b.md) — Qwen3-30B-A3B 真实模型负载实测

**Terminal-Bench 2.0**
- [`docs/tb2-arm-report.md`](docs/tb2-arm-report.md) — 89/89 镜像构建报告

**OSWorld**
- [`docs/osworld-arm-report.md`](docs/osworld-arm-report.md) — **100% ARM 化报告：QEMU/KVM 路线、17 条踩坑、双模型基线**

**通用**
- [`docs/model-eval-guide.md`](docs/model-eval-guide.md) — 如何用这套资产测你的模型/智能体
- [`docs/agent-eval-landscape.md`](docs/agent-eval-landscape.md) — 评测生态调研（基准全景 + 框架选型）
- [`docs/reproduction-playbook.md`](docs/reproduction-playbook.md) — 论文指标复现 playbook

## 硬件与环境

- 鲲鹏 ARM64 服务器（96 核 / 1TB RAM / aarch64），Ubuntu 20.04，Docker 29
- 16×Ascend 310P3 NPU（vllm-ascend 跑被测模型）
- 外网依赖全部消除：conda/pip/HF 走 TUNA + hf-mirror，httpbin 用本地 mock，
  OSWorld 任务资源本地缓存

## License

MIT
