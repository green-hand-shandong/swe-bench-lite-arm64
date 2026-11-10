# OSWorld ARM64 适配报告

> 目标：在鲲鹏 ARM64 服务器上原生运行 OSWorld（369 个桌面 GUI 智能体任务）。
> 本文记录适配方案、踩坑清单、当前可用范围与复现步骤。

## 一、结论速览

| 项目 | 状态 |
|---|---|
| ARM64 VM 启动（KVM 加速） | ✅ Ubuntu 22.04 aarch64，`-cpu host` 硬件虚拟化 |
| 桌面环境 | ✅ XFCE + Xorg dummy 1920×1080 + x11vnc |
| OSWorld guest server | ✅ 原版 main.py，systemd 常驻 |
| 主控接入 | ✅ 自写 QEMU provider，DesktopEnv 全链路可用 |
| 判分 | ✅ 第一个任务 score = 1.0（os 域文件压缩题） |
| **os 域（24 题）** | ✅ **已接模型跑基线**（qwen3-8b 纯文本模式，管线逐题出分） |
| libreoffice 三件套（117 题） | ✅ 应用已装，判分靠 vm_file/cloud_file，预计可用 |
| gimp（26）/ vlc（17）/ thunderbird（15） | ✅ 应用已装，待抽样验证 |
| chrome 域（45）+ multi_apps 中 chrome 相关 | ✅ chromium(snap) 已装并验证（bookmarks 题 score=1.0）；snap 路径/CDP 端口要点见下 |
| vs_code（23） | ✅ 官方 arm64 deb（1.145.2）已装 |

## 二、为什么不能直接用官方镜像

官方 Docker provider 的镜像 `happysixd/osworld-docker` 是 **amd64 单架构**：
QEMU-in-Docker（x86_64 OVMF 固件）+ x86_64 Ubuntu guest qcow2（12.3GB）。
在 ARM 主机上只能 TCG 全软件仿真（无 KVM 可用），桌面级负载慢一个数量级以上，
不可用。唯一路线是 **ARM guest 原生重建**。

## 三、适配方案

### 3.1 VM 层

```
base image (只读, init_state 已固化)
   └── overlay.qcow2 (每次冷重置重建)   ← boot-vm.sh
         └── QEMU/KVM aarch64 (-cpu host, 8C8G)
               ├── EFI: efi_code.fd (pflash0, RO) + efi_vars.fd (pflash1, RO)
               ├── 盘: virtio-blk (bootindex=0) + cloud-init seed (RO)
               ├── 网: user 模式, 端口转发 12222→22, 15000→5000,
               │        19222→9222, 18006→8006, 18080→8080
               └── 显示: virtio-gpu + Xorg dummy 1920×1080
```

- guest：cloud-init 建 `user/password`，装 XFCE/LibreOffice/GIMP/VLC/
  Thunderbird/pyautogui/gnome-screenshot/pyatspi
- guest server：OSWorld 原版 `main.py` + `pyxcursor.py` + `screen_recording.py`，
  systemd 单元 `osworld-server`（`DISPLAY=:0`，代理环境变量注入
  `HTTP(S)_PROXY=10.0.2.2:7890`、`HF_ENDPOINT=hf-mirror.com`）

### 3.2 主控层（新增 QEMU provider）

`desktop_env/providers/qemu/`：
- `provider.py`：`start_emulator` 等 guest server 就绪；`get_ip_address`
  返回固定端口串；`revert_to_snapshot` = 冷重置（重建 overlay + 重启 +
  等待就绪）；`save_state` no-op（基线固化在只读 base 里）
- `manager.py`：no-op 注册表（VM 生命周期由 boot-vm.sh 外部管理）
- 已注册进 `desktop_env/providers/__init__.py` 工厂与
  `desktop_env.py` 的 provider 白名单

运行主控：

```bash
NO_PROXY=localhost,127.0.0.1 HTTPS_PROXY=http://127.0.0.1:7890 \
PYTHONPATH=/data2/gxw/osworld-arm ./venv/bin/python run.py \
  --provider_name qemu \
  --path_to_vm /data2/gxw/osworld-arm-vm/ubuntu-22.04-arm64.img ...
```

### 3.3 快照/重置

QEMU 4.2 内部快照（savevm/loadvm）在含 pflash 机型上会**卡死 VM**
（`paused (restore-vm)` 无法恢复），放弃。采用 overlay 冷重置：
base 只读 + 每任务重建 overlay + 重启（~90s）。对批量评测，启动时间
可通过预起多 VM（不同端口组）摊薄。

## 四、踩坑清单（ARM 通用经验）

| # | 坑 | 现象 | 解法 |
|---|---|---|---|
| 1 | UEFI 固件位置 | 无任何串口输出、PXE 启动 | 代码必须 `pflash unit=0`，vars `unit=1`；2MB 固件需 pad 到 64MB |
| 2 | 启动盘不被 UEFI 识别 | `BdsDxe: failed to load Boot0001` → 只会 PXE | `-device virtio-blk-pci,bootindex=0` 显式指定 |
| 3 | GIC 版本 | `-cpu host` + `gic-version=2` 组合异常 | `gic-version=max` |
| 4 | snap/apt 无法出网 | cloud-init 卡在 snap store 30 分钟 | guest 内 `snap set system proxy.http(s)` + apt 95proxy，指向 `10.0.2.2:7890` |
| 5 | Xorg.wrap 拒绝 | `Only console users are allowed to run the X server` | `Xwrapper.config: allowed_users=anybody`；service 里直接调 `/usr/lib/xorg/Xorg` |
| 6 | pyautogui 报 `.Xauthority` 不存在 | `XauthError` | `touch ~/.Xauthority` + 显式 `XAUTHORITY` |
| 7 | OSWorld 主控调 `python` | `ModuleNotFoundError` | guest 内 `ln -s /usr/bin/python3 /usr/bin/python` |
| 8 | guest server 缺依赖 | `pyatspi` / `screen_recording` 缺失 | `apt install python3-pyatspi at-spi2-core`；补拷 `screen_recording.py` |
| 9 | 截图接口 500 | `install Pillow ≥9.2 and gnome-screenshot` | `apt install gnome-screenshot` 后重启 server |
| 10 | host 代理污染 localhost 请求 | `Guest server did not become ready` | 运行主控时必须 `NO_PROXY=localhost,127.0.0.1` |
| 11 | HF 资源下载失败 | setup download 步骤全挂 | host 侧 `HF_ENDPOINT=https://hf-mirror.com` + 代理 |
| 12 | `find -mtime +29` 边界 | 恰好 30.0 天的文件不匹配 | 用 `! -newermt '30 days ago'` |
| 13 | 内部快照卡死 | `savevm` 报 pflash 不支持；强行走 loadvm 后 VM `paused (restore-vm)` | 放弃内部快照，改 overlay 冷重置 |

## 五、已知问题

1. **X11 连接泄漏**（上游 #596）：guest server 每次截图泄漏一个 X11 连接，
   ~220 次后挂。上游 PR #500 已修但官方镜像未更新。我们用的是新 main.py
   （含修复），长时间批量评测时仍建议监控 `/screenshot` 返回码，异常时
   `systemctl restart osworld-server`（已验证 4 秒恢复）。
2. **chrome 域坐标漂移**：chromium 与 google-chrome 的 UI 布局有差异，
   依赖固定坐标的 pyautogui 任务可能受影响。官方 server 已有 arm→chromium
   命令替换分支，任务可行性需逐域抽样验证。
3. **multi_apps（101 题）**：依赖快照链 `multiapps`（预装多应用的组合状态），
   需要在 guest 里把组合应用装齐后重做一次快照基线。

## 六、复现步骤

```bash
# 1. 准备（宿主机：鲲鹏 ARM64 + /dev/kvm）
sudo apt-get install -y qemu-system-arm qemu-utils cloud-image-utils sshpass
curl -LO https://cloud-images.ubuntu.com/releases/jammy/release/ubuntu-22.04-server-cloudimg-arm64.img
qemu-img resize ubuntu-22.04-server-cloudimg-arm64.img 40G

# 2. cloud-init seed（用户 user/password + 桌面包）——见仓库 scripts/osworld-arm/
cloud-localds seed.img user-data meta-data

# 3. 启动（首次）或冷重置（后续）
bash boot-vm.sh

# 4. 验证 guest server
curl http://127.0.0.1:15000/platform   # → Linux

# 5. 跑任务（见 scripts/osworld-arm/run_task_example.py）
```

> 完整脚本（user-data、boot-vm.sh、provider、示例任务）整理在
> `scripts/osworld-arm/`。

## 七、chrome 域适配要点（2026-11-10 验证）

1. **snap chromium**：Ubuntu 22.04 的 chromium 只有 snap 版。装完后二进制在
   `/snap/bin/chromium`，**systemd service 的 PATH 必须显式加入 /snap/bin**，
   否则 server 的 `subprocess.Popen('chromium')` 报 `No such file or directory`。
2. **profile 路径**：snap chromium 的用户数据在
   `~/snap/chromium/common/chromium/Default/`（不是 `~/.config/chromium`）。
   OSWorld 官方 evaluator 的 `_is_arm_architecture` 分支已经用 snap 路径，
   说明上游已考虑 ARM。
3. **Xlib xauth 告警污染输出**：`.Xauthority` 为空时，python-Xlib 每次建连
   都向 stdout 打 `Xlib.xauth: warning...`，污染 `execute_python_command` 的
   输出 → `vm_platform` 变成 `"Xlib...\nLinux"`，所有按 platform 分支的
   evaluator（如 get_bookmarks）走错分支报 `Unsupported operating system`。
   解法：guest 里 `xauth add ':0' . $COOKIE`（会归一化为 `host/unix:0` 条目），
   并写进 systemd ExecStartPre 固化。
4. **应用必须烘焙进 base image**：overlay 冷重置会抹掉运行期安装的所有东西。
   流程：起 overlay → 装应用 → 关机 → `qemu-img commit overlay.qcow2` →
   base 更新（chromium+VSCode+socat+xauth 脚本已烘焙）。

## 八、ARM 智能体基线（qwen3-8b 纯文本）

- 模型：vllm-ascend 上的 qwen3-8b（text-only，无视觉），单轮 prompt 驱动
  pyautogui/bash 动作，max 6 步/题
- 驱动：`scripts/osworld-arm/run_os_baseline.py`（截图可选，文本模式默认）
- 已知限制：无视觉的 8B 模型做 GUI 任务分数预期很低，本次目的主要是
  **验证判分管线在 ARM 上逐题可出分**，不是刷分
- 结果：`results-os.jsonl`（逐题 score + 动作轨迹 + 耗时）

## 九、下一步

1. os 域 24 题基线跑完后，接带视觉的模型（Qwen3-VL / Qwen2.5-VL）重跑对比
2. multi_apps 快照基线重建（组合应用预装）
3. chrome 域再抽样 3-5 题（验证 pyautogui 坐标在 chromium 下的漂移程度）
4. 把 QEMU provider 与 boot-vm.sh 上游化（OSWorld 官方 provider 工厂是
   开放结构，`create_vm_manager_and_provider` 加分支即可）
