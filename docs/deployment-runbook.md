# BingWall 部署与运行说明

## 文档元信息

- 更新时间：2026-04-03T06:25:00Z
- 依据文档：`docs/system-design.md`
- 文档定位：一期单机部署、配置、运行、备份与恢复要求说明

## 当前状态说明

当前仓库已包含阶段一 `T1.1` 的最小可执行后端骨架、阶段一 `T1.2` 的 SQLite 迁移基线、阶段一 `T1.3` 的 Bing 采集与资源入库主链路、阶段一 `T1.4` 的公开 API、阶段一 `T1.5` 的基础公开前端、阶段一 `T1.6` 的单机部署模板与自动化部署验收入口，以及阶段二 `T2.3` 的手动采集任务消费入口与后台观测页面、阶段二 `T2.4` 的健康检查、资源巡检与本地资源归档清理闭环、阶段二 `T2.5` 的备份恢复脚本与恢复演练入口；当前手动 Bing 采集默认会按 `BINGWALL_COLLECT_BING_MARKETS` 批量覆盖固定 8 个地区，并已补齐基于 Playwright 的浏览器冒烟测试入口。本文件继续记录一期实施时必须遵循的部署与运行要求，并补充可直接复用的部署模板位置。

## 1. 部署目标

一期采用单机部署，目标是以最小复杂度打通以下链路：

- Nginx 提供前端静态资源和图片资源
- FastAPI 提供公开 API、后台 API 和健康检查接口
- SQLite 保存结构化数据
- 本地文件系统保存图片资源
- systemd 托管应用进程
- cron 触发定时采集、任务消费、巡检和备份

## 2. 目标环境

以下内容为一期实施时必须固定并记录的运行时基线要求。当前仓库已具备最小可执行后端代码和数据库迁移基线，因此本节记录已确认版本与后续仍需补齐的部署侧锁定动作。

| 组件 | 当前记录 | 说明 |
|---|---|---|
| Ubuntu | `24.04 LTS` 目标平台 | 部署环境需在实施时记录精确发行版本 |
| Python | `3.14` | 当前开发基线，固定 `3.14` 版本线，允许 `3.14.x` 补丁版本 |
| Node.js | `24.13.0` | 当前前端与构建运行时基线，后续如引入 Node.js 构建链路需补充版本锁定文件 |
| SQLite | 待实施环境安装后记录精确版本 | 一期数据库 |
| Nginx | 待实施环境安装后记录精确版本 | 反向代理与静态资源服务 |
| systemd | 当前工作环境可见为 `255.4-1ubuntu8.12` | 进程托管 |
| cron | 待实施环境安装后记录精确版本 | 定时触发 |

说明：

- 当前仓库已生成 `.python-version`、`.nvmrc`、`pyproject.toml` 与 `uv.lock`，并统一以 `uv sync` 创建和维护 `.venv`
- 当前仓库已生成 `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 与 `deploy/systemd/bingwall.env.example`
- 当前已确认 `Python 3.14` 为一期开发基线，阶段一初始化代码时必须围绕该版本线生成运行时与依赖锁定文件
- 当前后端依赖基线已固定为 `FastAPI 0.118.3`，该版本官方支持 `Python 3.14`，并兼容当前锁定的 `Starlette 0.47.3`
- 当前已确认 `Node.js 24.13.0` 为前端与构建运行时基线；若后续引入 Node.js 构建链路，必须补充对应版本锁定文件
- SQLite、Nginx、cron 的精确版本必须在目标部署环境创建时记录到部署清单

## 3. 目录约定

一期建议采用以下目录约定：

| 目录 | 作用 |
|---|---|
| `/opt/bingwall/app` | 应用代码目录 |
| `/var/lib/bingwall/data` | SQLite 数据目录 |
| `/var/lib/bingwall/images/tmp` | 临时下载目录 |
| `/var/lib/bingwall/images/public` | 正式资源目录 |
| `/var/lib/bingwall/images/failed` | 失败隔离目录 |
| `/var/log/bingwall` | 应用和任务日志目录 |
| `/var/backups/bingwall` | 备份目录 |
| `/etc/bingwall` | 受控配置目录 |

### 目录权限建议

为满足“应用写入、Nginx 读取”的最小要求，建议按以下方式创建目录：

- `/opt/bingwall/app`：代码目录，建议 `bingwall:bingwall`
- `/var/lib/bingwall/data`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/tmp`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/failed`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/public`：应用写入、Nginx 读取，建议 `2750`，`bingwall:www-data`
- `/var/log/bingwall`：应用日志和 Nginx 日志目录，建议 `0750`
- `/etc/bingwall`：受控配置目录，建议 `0750`，仅运维与应用账户可访问

当前仓库提供的 `deploy/systemd/bingwall.tmpfiles.conf` 已按上述口径写出目录模板。

补充说明：

- 当 `storage_backend = local` 时，资源仍写入 `/var/lib/bingwall/images/public`
- 当 `storage_backend = oss` 时，数据库中的 `relative_path` 应继续保持与本地目录一致的相对路径语义，便于迁移期间本地与 OSS 共存

## 4. 配置要求

### 必备配置项

| 类别 | 关键项 |
|---|---|
| 服务配置 | 监听地址、端口、基础 URL |
| 数据库配置 | SQLite 文件路径 |
| 存储配置 | 临时目录、正式目录、备份目录 |
| 采集配置 | 来源开关、默认市场、市场列表、定时回溯天数、超时、重试次数 |
| 安全配置 | 会话密钥、登录过期时间、初始化管理员密码约束 |
| 日志配置 | 当前已实现 `BINGWALL_LOG_LEVEL`；日志目录依赖部署目录约定 |
| 告警配置 | 当前未提供邮件 / Webhook 等内建告警配置项 |

### 关键配置基线

#### 会话密钥

- 必须使用不少于 `32` 字节的高强度随机值
- 必须通过环境变量或受控配置文件注入，不得写入仓库
- 推荐使用 Base64 或十六进制编码，便于部署系统管理

#### 登录会话

- 后台登录会话默认有效期建议不超过 `12` 小时
- 必须支持主动登出和服务端失效
- 服务端只保存会话令牌摘要，不保存明文令牌

#### 密码策略

- 当前配置层会对 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD` 强制执行“至少 `12` 位”校验
- 当前后台改密接口会校验“当前密码正确”“两次新密码一致”“新旧密码不能相同”，但不会额外强制大小写 / 数字 / 特殊字符复杂度
- 当前密码摘要算法已固定为 `pbkdf2_sha256`，迭代次数为 `600000`
- 如需升级到更严格复杂度或 `argon2id`，应视为后续安全增强，不应写成当前已落地能力

#### 建议监控 / 告警阈值（当前未配置化）

- 以下阈值目前仅可作为运维侧监控建议，仓库内尚未提供邮件、Webhook 或其他主动告警发送能力
- 当前代码里唯一直接使用的阈值是深度健康检查中的磁盘使用率 `85%`
- 连续 `3` 次自动采集失败
- 最近 `50` 次下载中失败率超过 `20%`
- 磁盘使用率超过 `85%`
- 最近 `5` 分钟 API `5xx` 比例超过 `5%`
- 超过 `24` 小时未产生成功备份

### 配置原则

- 所有环境差异都必须通过环境变量或受控配置文件注入
- 配置错误应在启动阶段失败
- 任何敏感值都不能写入仓库
- 所有时间相关配置内部按 UTC 处理

### 当前环境变量补充

以下变量已在当前代码中定义；其中 `.env.example` 覆盖了本地开发默认值，`deploy/systemd/bingwall.env.example` 覆盖了当前生产模板默认值。部署文档需要按代码真实键名记录，避免只写抽象类别而遗漏实际配置入口：

| 变量名 | 默认示例 | 说明 |
|---|---|---|
| `BINGWALL_APP_ENV` | `development` | 应用运行环境标识；生产模板中通常使用 `production` |
| `BINGWALL_APP_HOST` | `127.0.0.1` | FastAPI 监听地址 |
| `BINGWALL_APP_PORT` | `30003` | FastAPI 监听端口；生产模板默认可改为 `8000` |
| `BINGWALL_APP_BASE_URL` | `http://127.0.0.1:30003` | 对外基础 URL，用于生成站点级链接与回调语义 |
| `BINGWALL_LOG_LEVEL` | `INFO` | 当前唯一已实现的日志级别配置项 |
| `BINGWALL_COLLECT_NASA_APOD_ENABLED` | `true` | 是否启用 `nasa_apod` 来源采集 |
| `BINGWALL_COLLECT_NASA_APOD_DEFAULT_MARKET` | `global` | `nasa_apod` 默认市场代码，当前固定使用 `global` |
| `BINGWALL_COLLECT_NASA_APOD_API_KEY` | `DEMO_KEY` | NASA APOD API 密钥；生产环境应替换为真实密钥 |
| `BINGWALL_COLLECT_NASA_APOD_TIMEOUT_SECONDS` | `10` | NASA APOD HTTP 请求超时时间 |
| `BINGWALL_COLLECT_NASA_APOD_MAX_DOWNLOAD_RETRIES` | `3` | NASA APOD 图片下载最大重试次数 |

补充说明：

- `BINGWALL_APP_HOST` 与 `BINGWALL_APP_PORT` 当前会被应用配置模型和 `make run` 使用，但仓库内现有 `deploy/systemd/bingwall-api.service` 仍把 `uvicorn` 监听地址固定为 `127.0.0.1:8000`；若生产环境需要改监听地址或端口，必须同步修改 `systemd` 与 `nginx` 模板，不能只改环境变量
- `BINGWALL_COLLECT_NASA_APOD_*` 变量当前已在 `.env.example` 中给出本地开发示例，但 `deploy/systemd/bingwall.env.example` 仍未预填这些键；如目标机需要显式关闭 NASA APOD、替换 API Key 或调整其超时 / 重试参数，需在 `/etc/bingwall/bingwall.env` 中手工补充

### Bing 采集配置补充

- `BINGWALL_COLLECT_BING_DEFAULT_MARKET` 仍表示公开站点默认使用的 Bing 市场代码；手动单市场采集时也可显式使用该值，必须使用 `en-US` 这类带连字符的 Bing 市场格式
- `BINGWALL_COLLECT_BING_MARKETS` 用于手动采集默认市场集合和 cron 定时建任务；值为逗号分隔的市场列表，例如 `zh-CN,en-US,ja-JP,en-GB,de-DE,fr-FR,en-CA,en-AU`，系统会自动去重并忽略空白项
- `BINGWALL_COLLECT_BING_SCHEDULED_BACKTRACK_DAYS` 用于 Bing 定时任务快照中的回溯窗口，当前只允许 `3`、`5`、`7`
- 如果未单独配置 `BINGWALL_COLLECT_BING_MARKETS`，环境示例默认使用 `zh-CN,en-US,ja-JP,en-GB,de-DE,fr-FR,en-CA,en-AU` 八个地区
- 当前 `nasa_apod` 来源的环境变量命名统一使用 `BINGWALL_COLLECT_NASA_APOD_*` 前缀，不与 Bing 采集配置混用

## 5. 服务拓扑

### Nginx

负责：

- 公开前端静态资源
- 管理后台静态资源
- 图片正式资源目录
- 反向代理 `/api/*`

不得暴露：

- 临时下载目录
- 配置目录
- 日志目录
- 数据库目录

### FastAPI

负责：

- 公开 API
- 后台 API
- 健康检查接口
- 业务日志输出

### cron

负责：

- 自动采集触发
- 手动采集任务消费
- 失败重试
- 资源巡检
- 资源归档清理
- 备份任务

## 6. 启动与运行要求

当前仓库已具备最小后端服务，因此以下内容分为“当前已提供”和“后续仍需补齐”两部分：

### 后端服务

当前已提供：

- 开发环境依赖安装方式：`uv python install 3.14`、`uv sync --python 3.14 --frozen`，或直接执行内部等价的 `make setup`
- 数据库初始化命令：`make db-migrate`
- 首次管理员初始化方式：在 `.env` 或生产环境变量文件中同时设置 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD` 后执行 `make db-migrate`
- 自动公开开关：`BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED`，默认 `true`；开启时，新采集内容会在资源全部就绪后自动公开
- 手动采集命令：`make collect-bing COUNT=1`；默认会按 `BINGWALL_COLLECT_BING_MARKETS` 批量抓取配置中的 8 个地区，如需单独抓某个地区可用 `make collect-bing MARKET=en-US COUNT=1`；如需精确抓取最近 8 天内的指定 UTC 日期范围，可改用 `make collect-bing MARKET=en-US DATE_FROM=2026-04-02 DATE_TO=2026-04-02`
- 定时固定日期建任务命令：`make create-scheduled-collection-tasks`
- 本地联调便捷命令：`make scheduled-collect`
- 手动采集任务消费命令：`make consume-collection-tasks`
- 资源巡检命令：`make inspect-resources`
- 资源归档命令：`make archive-wallpapers`
- 备份命令：`make backup`
- 恢复命令：`make restore SNAPSHOT=/var/backups/bingwall/<snapshot> TARGET_ROOT=/tmp/bingwall-restore FORCE=1`
- `cron` 一键安装命令：`make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env`
- 本地开发验证命令：`make verify`
- 仓库内自动化部署验收命令：`make verify-deploy`
- 仓库内恢复演练命令：`make verify-backup-restore`
- 本地开发启动命令：`make run`
- 浏览器冒烟测试命令：`make browser-smoke` 或 `npm run browser-smoke`
- 健康检查接口：`GET /api/health/live`、`GET /api/health/ready`、`GET /api/health/deep`
- 生产环境变量示例：`deploy/systemd/bingwall.env.example`
- `systemd` 服务模板：`deploy/systemd/bingwall-api.service`
- 目录权限模板：`deploy/systemd/bingwall.tmpfiles.conf`
- Nginx 路由模板：`deploy/nginx/bingwall.conf`
- `cron` 示例模板：`deploy/cron/bingwall-cron`

### Playwright 浏览器冒烟测试

- 脚本位置：`scripts/dev/playwright_smoke.js`
- 带后台登录账号的示例模板：`scripts/dev/playwright_smoke_with_admin.example.sh`
- 默认前提：先执行 `make run`，确保本地服务已监听在 `127.0.0.1:30003`
- 统一入口：`make browser-smoke`
- 等价入口：`node scripts/dev/playwright_smoke.js`、`npm run browser-smoke`
- 带后台登录账号的模板入口：`bash scripts/dev/playwright_smoke_with_admin.example.sh`
- 可选环境变量：
  - `BINGWALL_BROWSER_BASE_URL`：改写默认访问地址
  - `BINGWALL_BROWSER_HEADLESS=false`：切换到非无头模式
  - `BINGWALL_ADMIN_USERNAME`、`BINGWALL_ADMIN_PASSWORD`：启用真实后台登录验证
- 当前脚本默认覆盖公开首页、公开列表筛选、壁纸详情页和后台登录页壳；若提供后台账号，还会继续验证后台登录跳转
- 若本机缺少 Playwright Node 模块，可先执行 `npm install --no-save playwright`
- 若本机尚未下载 Chromium，可执行 `npx playwright install chromium`
- Ubuntu 24.04 若浏览器启动缺 GTK 运行库，优先安装 `libgtk-3-0t64`；旧版发行版对应包名通常为 `libgtk-3-0`
- `cron` 安装脚本：`scripts/install_cron.py`

### 仓库内自动化部署验收

当前仓库额外提供：

- 验收脚本：`scripts/verify_t1_6.py`
- 统一入口：`make verify-deploy`

该验收入口会在不改写系统级 Nginx 和 `/etc/systemd/system` 的前提下，完成以下检查：

- 对正式 `deploy/systemd/bingwall-api.service` 执行离线安全检查
- 对正式 `deploy/systemd/bingwall.tmpfiles.conf` 执行根目录隔离的模板校验
- 使用临时 `systemd --user` 服务拉起 FastAPI，并验证重启后恢复服务
- 使用 Docker 官方 `nginx` 镜像加载正式路由模板，并验证公开页面、公开 API、前端静态资源和图片资源访问
- 观察用户级 `journalctl` 日志和临时 Nginx 访问日志，确认应用启动成功和代理转发成功可区分

说明：

- 验收脚本默认把 Nginx 监听端口改写到临时本地端口 `18080`，避免占用真实 `80` 端口
- 验收脚本不会修改 `/etc/systemd/system`、`/etc/nginx`、`/etc/tmpfiles.d`
- 真实目标机上线前，仍需按本文件的生产步骤安装正式服务配置和真实 Nginx 配置

### 生产环境最小启动步骤

1. 把仓库代码部署到 `/opt/bingwall/app`
2. 使用 `uv python install 3.14` 与 `uv sync --python 3.14 --frozen --no-dev` 准备生产虚拟环境
3. 复制 `deploy/systemd/bingwall.env.example` 到 `/etc/bingwall/bingwall.env`，替换域名、会话密钥和实际路径；仅在资源使用 `storage_backend = oss` 时设置 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL`
   当前若需要显式配置 NASA APOD 采集参数，还需手工补充 `BINGWALL_COLLECT_NASA_APOD_*`
4. 使用 `set -a && source /etc/bingwall/bingwall.env && set +a` 导入环境后执行 `uv run --no-sync python -m app.repositories.migrations`
5. 安装 `deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 和 `deploy/nginx/bingwall.conf`
   当前若需修改 FastAPI 监听地址或端口，必须同步修改 `deploy/systemd/bingwall-api.service` 中固定的 `--host/--port`，并同步调整 `deploy/nginx/bingwall.conf` 的 upstream
6. 执行 `systemd-tmpfiles --create`、`systemctl enable --now bingwall-api.service`、`nginx -t`、`systemctl reload nginx`
7. 以 `bingwall` 用户执行 `make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env CRON_LOG_DIR=/var/log/bingwall`

### 生产环境模板说明

#### `deploy/systemd/bingwall-api.service`

- 通过 `/etc/bingwall/bingwall.env` 注入受控环境变量
- 使用 `bingwall` 账号运行应用
- 通过 `/usr/bin/env uv run --no-sync python ...` 统一走 `uv` 运行入口，并固定 `PATH=/usr/local/bin:/usr/bin:/bin`
- 当前模板把 `uvicorn` 监听地址固定为 `127.0.0.1:8000`，不会直接读取 `BINGWALL_APP_HOST` 与 `BINGWALL_APP_PORT`
- 通过 `SupplementaryGroups=www-data` 配合正式资源目录权限，保证应用写入、Nginx 读取
- 采用 `Restart=on-failure`，在进程异常退出后自动重启

#### `deploy/systemd/bingwall.tmpfiles.conf`

- 统一创建数据库、图片、日志、备份和配置目录
- 正式资源目录使用 `bingwall:www-data` 和 `2750`
- 临时目录、失败目录、数据库目录不对 Nginx 开放
- 仅本地文件存储时，应保持 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 未设置，不要写成空字符串
- 如启用 OSS/CDN 公网访问，需要配置 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL`，例如 `https://cdn.example.com/bingwall`
- 如需调整 Bing 手动/定时采集覆盖的地区，可在环境文件中设置 `BINGWALL_COLLECT_BING_MARKETS=zh-CN,en-US,ja-JP,en-GB,de-DE,fr-FR,en-CA,en-AU`
- 如需调整 Bing 定时采集回溯窗口，可把 `BINGWALL_COLLECT_BING_SCHEDULED_BACKTRACK_DAYS` 设为 `3`、`5` 或 `7`
- 如需显式配置 NASA APOD 采集开关、API Key、超时或重试参数，需要在生产环境文件中手工补充 `BINGWALL_COLLECT_NASA_APOD_*`
- 如需首次自动创建后台管理员，可在环境文件中配置 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`；`make db-migrate` 仅会在 `admin_users` 为空时创建一个启用中的 `super_admin`
- 如需保留“采集后先人工审核再发布”的旧策略，可在环境文件中把 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED=false`

#### `deploy/nginx/bingwall.conf`

- `/api/` 反向代理到 `127.0.0.1:8000`
- `/` 代理公开页面
- `/assets/` 直接读取前端静态资源
- `/images/` 直接读取正式资源目录，不暴露磁盘真实路径给浏览器
- `storage_backend = oss` 的资源不经过本地 `/images/` 路由，由公开接口直接返回 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL/<relative_path>` 形式的地址

### 定时任务

当前仓库已提供：

- `scripts/create_scheduled_collection_tasks.py`：按当天 UTC 日期为每个已启用来源创建 `queued` 的 `scheduled_collect` 任务；其中 Bing 会按市场列表分别建任务，并把 `date_from`、`date_to`、`backtrack_days` 一并写入任务快照
- `deploy/cron/bingwall-cron`：目标机 `cron` 配置模板，当前默认包含“每日创建固定日期采集任务”“每分钟消费采集队列”“每日资源巡检”“每日资源归档”“每日一致性备份”五条任务，并固定写入 `CRON_TZ=UTC`
- `scripts/install_cron.py` 与 `make install-cron`：渲染模板中的真实路径、校验输入、备份当前用户已有 `crontab`，再把完整计划任务安装到当前用户 `crontab`

行为说明：

- cron 消费固定日期任务时，若上游在当天 UTC 边界尚未提供对应日期图片，系统会在最近 `8` 天窗口内自动回退到最近可用日期，并写入 `resolve_date_fallback` 任务日志；手动任务仍保持严格日期匹配
- Bing 定时任务会按 `BINGWALL_COLLECT_BING_MARKETS` 逐个市场建任务，并把 `count` 与 `backtrack_days` 同步写入任务快照；当前回溯天数只允许 `3`、`5`、`7`
- Bing 定时任务会先读取回溯窗口内的元数据，再优先匹配固定日期；若当天无图，则回退到窗口内最近可用日期
- NASA APOD 定时任务写入 `count=1`，但消费阶段会把上游查询窗口扩展到最近 `8` 天，并在当天无图时回退到最近可用日期
- 若同来源同市场同 `date_from/date_to/backtrack_days` 组合已存在 `queued`、`running`、`succeeded` 或 `partially_failed` 的 `cron` 任务，新脚本会跳过创建，避免重复堆积；若历史任务为 `failed`，则允许重建
- 模板中的每条命令都会先加载 `/etc/bingwall/bingwall.env`，再通过安装时解析出的绝对 `uv` 路径执行 `uv run --no-sync python ...`，确保 `cron` 与 `systemd` 使用同一套生产环境变量，而不是退回仓库根目录 `.env`

建议部署步骤：

1. 确认 `/opt/bingwall/app`、`uv` 可执行文件、`/opt/bingwall/app/.venv`、`/var/log/bingwall` 与 `/etc/bingwall/bingwall.env` 已存在且权限正确
2. 以 `bingwall` 用户执行 `make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env CRON_LOG_DIR=/var/log/bingwall`
3. 观察安装输出中的 `backup_path`，记录当前用户旧 `crontab` 备份位置，便于回滚
4. 先手工执行一次 `make create-scheduled-collection-tasks` 与 `make consume-collection-tasks` 验证数据库、日志目录和图片目录权限
5. 观察后台 `/admin/tasks` 与 `/admin/logs`，确认自动任务记录带有 `trigger_type = cron`，并能看到 `market_code`、`date_from`、`date_to`、`backtrack_days` 与回退日志
6. 观察 `/var/log/bingwall/create-scheduled-collection-tasks.log`、`consume-collection-tasks.log`、`inspect-resources.log`、`archive-wallpapers.log` 与 `backup.log`，确认首轮计划任务结果

当前目标机仍需补齐：

- 执行一次真实目标机安装并确认首轮任务运行
- 生产机日志轮转确认

### 健康检查

当前已提供：

- `GET /api/health/live`：确认进程可响应
- `GET /api/health/ready`：确认配置、数据库和关键目录可用；失败时返回 `503`
- `GET /api/health/deep`：返回最近一次采集任务摘要、磁盘使用率和资源目录摘要；严重异常时返回 `503`
- `make inspect-resources`：巡检数据库就绪资源与正式资源目录的一致性，发现资源缺失时自动刷新资源与内容状态
- `make archive-wallpapers`：把本地 ready 资源迁移到统一结构化路径，清理临时目录遗留文件、空文件和重复孤儿文件，并把损坏资源隔离到失败目录；若发现损坏资源或目标路径存在内容冲突，命令会返回非零退出码

## 7. 日志要求

所有日志至少应包含：

- UTC 时间戳
- 日志级别
- 追踪 ID
- 模块名
- 事件类型
- 摘要信息

禁止记录：

- 密码
- 会话密钥
- 原始令牌
- 其他敏感凭证

## 8. 备份要求

### 备份对象

- SQLite 数据库文件
- 图片正式资源目录
- 对象存储桶或 CDN 源站中的同路径对象（若已启用 OSS）
- 配置文件
- 应用日志和审计日志
- `systemd` 和 Nginx 配置

### 备份频率建议

| 对象 | 频率 | 方式 |
|---|---|---|
| 数据库 | 每日 | 一致性备份 |
| 图片目录 | 每日增量，周期性全量 | 文件级备份 |
| 配置文件 | 变更后立即备份 | 版本留存 |
| 日志 | 每日归档 | 压缩保存 |

### 关键约束

- SQLite 备份必须采用一致性方式
- 数据库与图片目录备份应尽量保持同一时间点语义
- 备份产物必须保留多个周期
- 若已启用 `storage_backend = oss`，应用侧备份脚本只覆盖本地目录和配置，不会自动导出对象存储桶；对象存储快照需由云平台或独立备份策略负责

### 当前仓库实现

- 备份入口：`scripts/run_backup.py`，统一入口：`make backup`
- 备份产物默认落在 `BINGWALL_BACKUP_DIR` 对应目录下的单次快照目录，包含 `manifest.json`、`backup.log` 和 `artifacts/`
- 数据库备份使用 Python `sqlite3.Connection.backup(...)` 执行一致性备份，不直接拷贝活跃数据库文件
- 当前会同时归档正式资源目录、配置目录、日志目录，以及 Nginx / systemd / tmpfiles 部署配置

建议先在目标机确认以下路径存在且权限正确：

- 数据库文件
- 正式资源目录
- 配置目录
- 日志目录
- Nginx 配置文件
- `systemd` 服务文件
- `tmpfiles` 配置文件

## 9. 恢复要求

恢复顺序：

1. 恢复配置文件
2. 恢复数据库
3. 恢复图片资源目录
4. 启动应用
5. 执行资源巡检
6. 验证公开接口、后台接口和静态资源访问

### 当前仓库实现

- 恢复入口：`scripts/run_restore.py`，统一入口：`make restore`
- 恢复默认要求显式传入 `--force` 才会覆盖已有数据库文件或非空目录
- 恢复会生成独立 `restore.log` 和恢复记录 JSON，便于追踪执行时间、目标范围和结果摘要
- `scripts/verify_t2_5.py` 与 `make verify-backup-restore` 可在隔离目录中执行一次完整恢复演练

### 恢复手册（最小步骤）

1. 执行 `make backup`，确认最新快照目录已生成 `manifest.json`
2. 如需先做隔离演练，执行 `make restore SNAPSHOT=/var/backups/bingwall/<snapshot> TARGET_ROOT=/tmp/bingwall-restore FORCE=1`
3. 如需原位恢复，执行 `uv run --no-sync python scripts/run_restore.py --snapshot /var/backups/bingwall/<snapshot> --database-path /var/lib/bingwall/data/bingwall.sqlite3 --public-dir /var/lib/bingwall/images/public --config-dir /etc/bingwall --log-dir /var/log/bingwall --backup-dir /var/backups/bingwall --nginx-config-path /etc/nginx/sites-available/bingwall.conf --systemd-service-path /etc/systemd/system/bingwall-api.service --tmpfiles-config-path /etc/tmpfiles.d/bingwall.conf --force`
4. 恢复完成后启动或重启应用与代理服务
5. 执行 `curl http://127.0.0.1/api/health/deep`
6. 执行 `make inspect-resources`
7. 执行 `make archive-wallpapers`
8. 验证 `curl http://127.0.0.1/`、`curl http://127.0.0.1/api/public/site-info` 和后台登录/后台列表接口

## 10. 上线前检查清单

### 阶段一公开链路最小检查

- 配置文件已审查
- 数据目录和权限已创建
- Nginx 路由已校验
- `systemd` 服务已可启动
- 公开页面、公开 API 和静态资源可访问
- `README.md` 中存在可复制启动说明

建议按以下顺序执行并记录结果：

1. 在仓库根目录执行 `make verify-deploy`
2. 在目标机按本文件“生产环境最小启动步骤”安装正式服务
3. 在目标机执行 `nginx -t`
4. 执行 `curl http://127.0.0.1/api/health/live`
5. 执行 `curl http://127.0.0.1/api/health/ready`
6. 执行 `curl http://127.0.0.1/api/health/deep`
7. 执行 `curl http://127.0.0.1/api/public/site-info`
8. 执行 `curl http://127.0.0.1/`
9. 如已有正式资源，执行 `curl -I http://127.0.0.1/images/<正式资源相对路径>`
10. 执行 `make inspect-resources`
11. 执行 `make archive-wallpapers`
12. 观察 `journalctl -u bingwall-api.service` 与 `/var/log/bingwall/nginx.access.log`

### 完整上线检查（阶段二目标）

- 配置文件已审查
- 数据目录和权限已创建
- 日志目录和备份目录已创建
- Nginx 路由已校验
- `systemd` 服务已可启动
- cron 已加载
- 健康检查可访问
- 首次备份可执行
- 首次恢复演练可执行
- 首次手动采集已验证

## 11. 当前已知缺口

- 尚未完成目标机执行 `make install-cron` 后的首轮运行确认

补充说明：

- 当前仓库已通过临时 `systemd --user` 服务和 Docker 化 `nginx` 完成 `T1.6` 自动化验收
- 目标机仍需执行真实 Nginx 包安装、systemd 服务安装和公网域名接入，这些属于部署执行动作，不再阻塞阶段一验收

这些缺口必须在阶段一和阶段二实施中逐项关闭。
