# WebArena on ARM64 调研（2026-11）

## 结论：分梯度可行，shopping 两站是硬门槛

| 站点 | 上游软件 | arm64 官方镜像 | 预置数据 | 重建难度 |
|---|---|---|---|---|
| wikipedia | kiwix-serve | ✅ ghcr.io/kiwix/kiwix-serve:3.3.0 多架构 | ✅ zim 公开下载 | 极低 |
| homepage | Flask 自研（仓库内 app.py） | ✅ 纯 Python | ✅ 仓库自带 | 极低 |
| gitlab | gitlab-ce | ✅ 官方多架构 | ❌ 预置 repo 需数据注入 | 中 |
| map | openstreetmap-website | ✅（Rails） | 需配置 | 中 |
| forum (Reddit) | postmill (PHP) | ❌ 无官方镜像 | ❌ 预置用户/帖 | 中（源码构建+数据迁移） |
| shopping / shopping_admin | 自研（非开源） | ❌ 仅 x86 tar | ❌ 数据库预置 | **高（自研代码未开源，卡在 tar 包 amd64-only）** |

## 关键阻塞

- 4 个核心站点镜像以 x86 tar 发布（CMU 服务器 metis.lti.cs.cmu.edu 与 archive.org 均不可达/403）
- shopping/shopping_admin 的源码不在 WebArena 仓库——无法源码重建 ARM 镜像
- 论文任务里 shopping 站是任务大户（115/812 任务）

## 可行路径

1. **低门槛先跑**：wikipedia + homepage + gitlab（arm64 官方镜像）+ map → 部分任务子集可跑
2. **shopping 站**：在 x86 机器上 `docker pull` tar 后 `docker save` 导出 → 用 `docker buildx`/qemu 检查能否重打 arm64（自研应用若是纯 Python/PHP 可能直接兼容，需实验）
3. **与上游联系**：WebArena 作者 (CMU) 询问 arm64 镜像计划

## 主控接入

browser_env/env_config.py 用环境变量传各站点 URL：
REDDIT/SHOPPING/SHOPPING_ADMIN/GITLAB/WIKIPEDIA/MAP/HOMEPAGE——指向本机端口即可。
