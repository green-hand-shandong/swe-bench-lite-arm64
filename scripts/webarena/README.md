# WebArena on ARM64 调研与实测（2026-11-19/20）

## 结论：站点可用性实测后，812 题当前可跑子集为 0——镜像获取是硬阻断

## 一、站点实测结果（2026-11-19）

| 站点 | 实测状态 | 说明 |
|---|---|---|
| **wikipedia** | ✅ **ARM64 跑通** | 95GB zim（2022-05 版，archive.org 公开下载）+ kiwix-serve **3.7.0**（见踩坑），`http://<host>:8888` 200 |
| **homepage** | ✅ **ARM64 跑通** | 仓库自带 Flask app，端口 4399，3 条路由 200（password.html 模板上游缺失，无任务引用） |
| gitlab | ❌ 镜像不可得 | `metis.lti.cs.cmu.edu` 整机宕机（80/443 拒连）；archive.org `webarena-env-gitlab-image` **is_dark（受限条目）**，需作者授权 |
| forum (Reddit) | ❌ 同上 | `webarena-env-forum-image` is_dark |
| shopping / shopping_admin | ❌ 同上 | `webarena-env-shopping(-admin)-image` is_dark；且源码未开源无法重建 |
| map | ❌ 无官方镜像 | WebArena 用 AMI 内自建 openstreetmap-website compose，无公开镜像/构建脚本 |

**关键发现：四个受限镜像在 archive.org 上全部是 is_dark（受限）条目，而唯一的公开源
metis.lti.cs.cmu.edu 已宕机。** 获取路径只剩：联系 WebArena 作者开放 archive.org
条目，或等 metis 恢复。

## 二、任务覆盖分析（config_files/test.raw.json，812 题）

| 站点组合 | 题数 | 可跑？ |
|---|---|---|
| shopping（含 admin） | 371+184 | ❌ 镜像受限 |
| gitlab（含 6 题 gitlab+wikipedia） | 186+6 | ❌ 镜像受限 |
| reddit/forum | 129 | ❌ 镜像受限 |
| map（含 17 题 map+wikipedia） | 109+17 | ❌ 无镜像 |
| wikipedia 纯站任务 | **0** | wiki 23 题全部与 map/gitlab 组合（"查 wikipedia 后在 gitlab 建 repo"），判分走对方站点 |

wikipedia 站点本身已在 ARM64 上完全可用（95GB 全量 zim，string_match 判分逻辑
已验证），一旦 gitlab/map 任一镜像可获取，对应 23 题 wiki 组合任务立即可跑。

## 三、已验证的 ARM64 组件（可直接复用）

1. **kiwix-serve 3.7.0**（ghcr.io/kiwix/kiwix-serve:3.7.0）：

```bash
# zim 下载（95GB，archive.org 公开条目）
curl -L -C - -o wikipedia_en_all_maxi_2022-05.zim \
  "https://archive.org/download/wikipedia_en_all_maxi_2022-05/wikipedia_en_all_maxi_2022-05.zim"

# 启动（zim 放 /root/webarena-assets）
docker run -d --name wikipedia -v /root/webarena-assets:/data -p 8888:8080 \
  ghcr.io/kiwix/kiwix-serve:3.7.0 wikipedia_en_all_maxi_2022-05.zim
curl -sL -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"  # -> 200
```

2. **homepage**：`environment_docker/webarena-homepage/app.py`，任意 Python3 + flask，
   `python app.py`（监听 4399）。
3. **主控 harness**：`requirements.txt` 装进 py3.10 venv + `playwright install chromium`
   全部成功（openai 0.27 老 API、beartype 0.12 均正常）。

## 四、ARM 专属踩坑

| # | 坑 | 解法 |
|---|---|---|
| 1 | kiwix-serve:3.3.0 的 arm64 变体实为 **32-bit ARM binary**（`FATAL: kernel too old`/语法错误） | 换 **3.7.0**（真 arm64，兼容 5.4 内核）；latest 需 >5.4 内核 |
| 2 | 宿主 8888 被 searxng 占用 | searxng 迁到 18889，wikipedia 用 8888（WebArena env 约定端口） |
| 3 | 无 `/usr/bin/python`（commands 只有 python3） | `ln -s /usr/bin/python3 /usr/bin/python`（判分脚本硬编码 python） |

## 五、后续路径

1. **联系上游**：给 WebArena 作者提 issue，请求开放 archive.org 四个镜像条目
   （或恢复 metis 服务器）——这是解锁 812 题的唯一钥匙
2. **gitlab 替代**：gitlab-ce 官方 arm64 镜像 + 手工注入 WebArena 预置 repo 数据
   （数据结构未知，需反解 is_dark tar 才能确定，优先级低于路径 1）
3. **map 替代**：openstreetmap-website 源码构建 + 导入区域 tile——成本高，最后考虑
4. wikipedia + homepage 两站已就绪，任何镜像解锁后可立即开跑
