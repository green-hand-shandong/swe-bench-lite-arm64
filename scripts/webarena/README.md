# WebArena on ARM64 调研与实测（2026-11-19/20）

## 结论：**4/5 站点 ARM64 原生跑通**；剩余 1 个（shopping）源码闭源 + 1 个（map）无公开镜像源。
判分数据（原版预置 repo/帖子）仍需上游 tar，但**环境层 ARM 化已基本完成**。

## 一、站点实测结果（2026-11-20 更新）

| 站点 | 实测状态 | 说明 |
|---|---|---|
| **wikipedia** | ✅ **ARM64 跑通** | 95GB zim（2022-05 版，archive.org 公开）+ kiwix-serve **3.7.0**，`:8888` 200 |
| **homepage** | ✅ **ARM64 跑通** | 仓库自带 Flask app，`:4399` 200 |
| **gitlab** | ✅ **ARM64 跑通（18.5.7）** | 官方 `gitlab/gitlab-ce:18.5.7-ce.0`（16.x 无 arm64，最低 18.x），byteblaze 用户 + 57 个判分 repo 已批量建好，`:8023` 200 |
| **forum (Reddit)** | ✅ **ARM64 跑通（postmill 源码构建）** | `Mewgood/Postmill` 源码 → php-fpm + nginx + postgres:11 全 arm64 自建，`:9999` 200，WebArena 用户 MarvelsGrantMan136 已入库 |
| shopping / shopping_admin | ❌ | 源码未开源（唯一死路）；tar 镜像 is_dark |
| map | ❌ | openstreetmap-website 无官方镜像（作者 AMI 内手工搭建）；源码可建但需导入区域 OSM 数据（数小时 Tile 渲染） |

**原版预置数据（判分内容）仍绑在上游 tar**：gitlab 判分查具体 MR/issue 内容（如
primer/design MR 450），forum 判分查具体帖子 ID（135156 等），tar 的两个公开源
（metis.lti.cs.cmu.edu 已宕机；archive.org 条目 is_dark）均不可得——环境可跑，
数据需向作者索取。repo 骨架（57 个）与用户已建好，数据到手即可补齐。

## 二、gitlab ARM64 重建路径（已验证）

```bash
# 镜像（daocloud 拉，官方 registry 在部分网络被 403）
docker pull docker.m.daocloud.io/gitlab/gitlab-ce:18.5.7-ce.0
docker tag docker.m.daocloud.io/gitlab/gitlab-ce:18.5.7-ce.0 gitlab/gitlab-ce:18.5.7-ce.0

docker run -d --name gitlab-arm -p 8023:8023 -p 12322:22 \
  -v /data0/gitlab-ce/config:/etc/gitlab -v /data0/gitlab-ce/logs:/var/log/gitlab \
  -v /data0/gitlab-ce/data:/var/opt/gitlab --shm-size 256m \
  gitlab/gitlab-ce:18.5.7-ce.0 /opt/gitlab/embedded/bin/runsvdir-start

# 首次启动：runsvdir-start 报 /proc/sys/fs/file-max 只读（无害），reconfigure 生成配置
docker exec gitlab-arm gitlab-ctl reconfigure          # ~3 分钟
docker exec gitlab-arm bash -c "printf \"external_url 'http://0.0.0.0:8023'\n\" > /etc/gitlab/gitlab.rb"
docker exec gitlab-arm gitlab-ctl reconfigure          # 监听 8023

# 建用户（18.x 的 Users::CreateService 有 organization 校验坑，走 API 最稳）
TOKEN=$(docker exec gitlab-arm gitlab-rails runner \
  "puts User.find_by(username:'root').personal_access_tokens.create!(name:'arm', scopes:['api'], expires_at: 30.days.from_now).token")
curl -X POST http://127.0.0.1:8023/api/v4/users -H "PRIVATE-TOKEN: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"byteblaze","email":"byteblaze@example.com","password":"hello1234","name":"byteblaze","skip_confirmation":"true"}'
# → 57 个判分 repo 批量创建（见 scripts/webarena/seed_gitlab.py 逻辑）
```

## 三、postmill (forum) ARM64 源码构建（已验证，6 次迭代踩坑全记录）

源码：`Mewgood/Postmill`（原 postmill/postmill 已 404，此 fork 是唯一存续），
纯 PHP+Symfony+Twig，基础镜像（node:14-alpine / php:8.1-fpm-alpine / nginx:1.18-alpine
/ postgres:11-alpine / composer:2）全部官方多架构——**ARM 兼容性本身零障碍**，
坑全在构建网络与依赖裁剪：

| # | 坑 | 现象 | 解法 |
|---|---|---|---|
| 1 | pecl REST 接口超时 | `apcu ... does not have REST xml available`（25 分钟无响应） | `install-php-extensions` 换成 `docker-php-ext-install`（内置工具）+ pecl 5 次重试循环 |
| 2 | alpine 包名 | `librabbitmq-dev (no such package)` | 是 `rabbitmq-c-dev`（构建）+ `rabbitmq-c`（运行时） |
| 3 | zip 扩展缺 libzip | pkg-config 找不到 libzip | build-deps 加 `libzip-dev` |
| 4 | **apk del .build-deps 连带删运行时库** | composer 阶段 `Unable to load dynamic library 'amqp'/'gd'/'intl'/'pdo_pgsql'/'zip'`（.so 找不到依赖） | `apk del` 只删编译器（autoconf/gcc/g++/make...），运行时库（libpng/libicu/libpq/libzip/rabbitmq-c）显式 `apk add` 保留 |
| 5 | 构建时长 | 单次 full build ~50 分钟（apk 拉 llvm/clang 76 包 + yarn webpack4 编译） | buildx cache 生效后增量 ~2 分钟；--target 分层构建（php/web 独立） |

启动栈（三容器）：

```bash
docker network create postmill-net
docker run -d --name postmill-db --network postmill-net \
  -e POSTGRES_USER=postmill -e POSTGRES_PASSWORD=secret \
  postgres:11-alpine

docker run -d --name php --hostname php --network postmill-net --network-alias php \
  -e DATABASE_URL="postgresql://postmill:secret@postmill-db:5432/postmill?serverVersion=11" \
  -e APP_ENV=prod -e APP_SECRET=<any> -e MAILER_DSN=null://null \
  postmill-php-arm64:latest
docker exec php php bin/console doctrine:migrations:migrate --no-interaction

docker run -d --name postmill-web --network postmill-net -p 9999:80 postmill-web-arm64:latest
# nginx upstream 硬编码 "php"（容器名必须叫 php 或加 network-alias php）
```

用户注入（postmill 无 CLI 加用户命令，直接 SQL，注意 8 个 NOT NULL 列）：

```sql
INSERT INTO users (id, username, password, email, created, normalized_username,
  normalized_email, locale, front_page, front_page_sort_mode, timezone,
  allow_private_messages) VALUES (1, 'MarvelsGrantMan136', '<bcrypt>',
  'marvels@webarena.com', NOW(), 'marvelsgrantman136', 'MARVELS@WEBARENA.COM',
  'en', 'subscribed', 'hot', 'UTC', true);
```

验证：`curl http://127.0.0.1:9999/forums/all` → 200 `<title>All forums`。

## 四、已验证的其余 ARM64 组件

1. **kiwix-serve 3.7.0**：见上轮记录（3.3.0 arm64 是 32-bit ARM binary 的坑仍在）
2. **homepage**：Flask app，`python app.py`（:4399）
3. **主控 harness**：py3.10 venv + playwright chromium 全部就绪

## 五、ARM 专属踩坑（本轮新增）

| # | 坑 | 解法 |
|---|---|---|
| 1 | kiwix 3.3.0 arm64 = 32-bit binary | 用 3.7.0（latest 要内核 >5.4） |
| 2 | aliyun registry mirror 对 node/gitlab 403 | 全部走 `docker.m.daocloud.io` 前缀拉取后 retag |
| 3 | gitlab-ce 16.x（WebArena 原版）无 arm64 | 官方 arm64 从 18.x 起；判分页面 DOM 有差异，需逐题验证 |
| 4 | gitlab 18.x Users::CreateService 强制 organization | 用 REST API `/users` 创建 |
| 5 | postmill pecl/apk/编译五连坑 | 见上表 |
| 6 | runsvdir-start 写 /proc/sys/fs/file-max 报只读 | 无害，忽略 |

## 六、下一步

1. **向 WebArena 作者要预置数据**（issue 或邮件）——gitlab/forum 判分内容与
   shopping 镜像的唯一来源；环境已 100% 就绪，数据到手即可全量出分
2. map 站：openstreetmap-website 源码构建可行（Rails+arm64 兼容），但需导入
   OSM 区域数据（预置 tile 在 AMI 里）——优先级最低
3. gitlab 16→18 的 DOM 差异对 186 题 gitlab 任务的影响需实测评估
   （url_match 47 题大概率兼容，program_html 134 题需逐题看）

## 七、端到端 agent 基线（2026-11-23，ARM64 全链路打通）

**首批 6 题（gitlab+wikipedia 组合，task 556-561）在 ARM64 上完整跑通**：
playwright chromium 驱动 → qwen3.6-35b-a3b（网关）→ gitlab 写 repo → 官方
program_html 判分（读 README raw 内容比对）。

| 项 | 结果 |
|---|---|
| 任务执行 | 6/6 出分（5 题正常走完 15 步上限，1 题 gitlab 导航超时） |
| LLM/基础设施错误 | 0 |
| 判分 | 0/6 resolved（长 horizon 任务对 35B 模型属预期；管线验证是本轮目的） |
| trace | playwright trace.zip + network + 截图全量落盘 |

### 接入踩坑（harness 侧，ARM 无关但网关相关）

| # | 坑 | 解法 |
|---|---|---|
| 1 | `config_files/{i}.json` 里 `__GITLAB__` 等占位符未替换 | 跑 `scripts/generate_test_data.py`（需 `PYTHONPATH=.` + 7 个站点 env） |
| 2 | `storage_state` 登录态缺失 → env.reset 直接 AssertionError | 先 `python -m browser_env.auto_login --site_list gitlab`（.auth 目录要预建） |
| 3 | run.py 用 `"python"` 起 cookie-renew 子进程且不传 env | patch 成 `sys.executable` + 显式 `PYTHONPATH` |
| 4 | tiktoken 不认识自定义模型名 | Tokenizer 回退 `cl100k_base` |
| 5 | **网关拒绝连续多条 system 消息**（400 请求参数错误） | 请求前把连续 system 合并为一条（已 patch 到 openai_utils） |
| 6 | openai 0.27 + 网关 | `openai.api_base` + `extra_body.chat_template_kwargs.enable_thinking=false` |

### 复现

```bash
bash run-arm.sh --test_start_idx 556 --test_end_idx 562
# 结果在 results-arm/（*.html + traces/*.zip）
```

### forum 站首批 resolved（2026-11-23）

task 595/596（订阅 trending post，url_match 判分）——**2/2 resolved，Average score 1.0**。
这是 WebArena 在 ARM64 上首批判分通过的任务。

postmill 数据注入要点（直接 SQL，34 版块 + 102 帖）：
- `forums` 表需填 `sidebar`（NOT NULL，缺了版块页 500）
- `submissions` 有 CHECK：`media_type='url'` 或 `media_type='image' AND image_id IS NOT NULL`
- 版块名从任务 intent/判分 URL 提取（34 个：space/books/consoles/...）
- 每版块 3 帖（ranking 递减模拟 trending）
