# Guest 内部署物（ARM64 Ubuntu 22.04 VM 内）

这些文件/配置需要写入 VM 内部。`user-data`（cloud-init）已覆盖大部分；
以下是 cloud-init 之外的增量配置。

## systemd 单元

### osworld-x.service（X + XFCE）
```ini
[Unit]
Description=OSWorld X server
After=systemd-user-sessions.service

[Service]
Type=forking
User=user
ExecStart=/usr/bin/xinit /usr/bin/startxfce4 -- /usr/lib/xorg/Xorg :0 -config /etc/X11/xorg.conf -noreset
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
前置条件：
- `/etc/X11/xorg.conf`：dummy 驱动 1920x1080（见 `xorg.conf`）
- `/etc/X11/Xwrapper.config`：`allowed_users=anybody` + `needs_root_rights=yes`

### osworld-server.service（OSWorld guest server）
```ini
[Unit]
Description=OSWorld Guest Server
After=osworld-x.service network.target

[Service]
User=user
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/user/.Xauthority
Environment=PATH=/snap/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=HTTP_PROXY=http://10.0.2.2:7890
Environment=HTTPS_PROXY=http://10.0.2.2:7890
Environment=HF_ENDPOINT=https://hf-mirror.com
Environment=NO_PROXY=localhost,127.0.0.1
WorkingDirectory=/home/user/server
ExecStartPre=/usr/local/bin/fix-xauth.sh
ExecStart=/usr/bin/python3 /home/user/server/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### fix-xauth.sh（X11 xauth 告警根治）
```bash
#!/bin/bash
rm -f /home/user/.Xauthority
COOKIE=$(mcookie)
xauth add ':0' . $COOKIE
xauth add 'osworld-arm:0' . $COOKIE
xauth add 'osworld-arm/unlimited:0' . $COOKIE
chown user:user /home/user/.Xauthority
```
> 没有 cookie 时 python-Xlib 每次建连向 stdout 打 warning，污染
> `execute_python_command` 输出，导致 `vm_platform` 等判分分支失效。

## guest 内 pip 依赖（TUNA）
```
pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  flask requests pyautogui pillow lxml opencv-python-headless parse pytz
```
apt 依赖：`python3-pyatspi at-spi2-core gnome-screenshot scrot zip socat`

## 符号链接
```
ln -sf /usr/bin/python3 /usr/bin/python   # OSWorld 主控硬编码调 python
ln -sf /snap/bin/chromium /usr/local/bin/chromium
```
