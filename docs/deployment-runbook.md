# BingWall 部署与运行说明

## 文档元信息

- 更新时间：2026-04-05T03:46:34Z
- 依据文档：`docs/system-design.md`
- 文档定位：一期单机部署、配置、运行、备份与恢复要求说明

## 当前状态说明

当前仓库已包含阶段一 `T1.1` 的最小可执行后端骨架、阶段一 `T1.2` 的 SQLite 迁移基线、阶段一 `T1.3` 的 Bing 采集与资源入库主链路、阶段一 `T1.4` 的公开 API、阶段一 `T1.5` 的基础公开前端、阶段一 `T1.6` 的单机部署模板与自动化部署验收入口，以及阶段二 `T2.3` 的手动采集任务消费入口与后台观测页面、阶段二 `T2.4` 的健康检查、资源巡检与本地资源归档清理闭环、阶段二 `T2.5` 的备份恢复脚本与恢复演练入口；当前手动 Bing 采集默认会按 `BINGWALL_COLLECT_BING_MARKETS` 批量覆盖固定 8 个地区，并已补齐基于 Playwright 的浏览器冒烟测试入口。本文件继续记录一期实施时必须遵循的部署与运行要求，并补充可直接复用的部署模板位置。

## 1. 部署目标

一期采用单机部署，目标是以最小复杂度打通以下链路：

- 优先由 Nginx Proxy Manager 或等价反向代理提供对外入口；当前已验收目标机也记录了直接开放 `8000/tcp` 的最小公网入口
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
| Nginx Proxy Manager / Nginx | 待实施环境记录精确版本 | 反向代理与静态资源服务 |
| systemd | 当前工作环境可见为 `255.4-1ubuntu8.12` | 进程托管 |
| cron | 待实施环境安装后记录精确版本 | 定时触发 |

说明：

- 当前仓库已生成 `.python-version`、`.nvmrc`、`pyproject.toml` 与 `uv.lock`，并统一以 `uv sync` 创建和维护 `.venv`
- 当前仓库已生成 `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall-nginx.service`、`deploy/systemd/bingwall.tmpfiles.conf` 与 `deploy/systemd/bingwall.env.example`
- 当前已确认 `Python 3.14` 为一期开发基线，阶段一初始化代码时必须围绕该版本线生成运行时与依赖锁定文件
- 当前后端依赖基线已固定为 `FastAPI 0.118.3`，该版本官方支持 `Python 3.14`，并兼容当前锁定的 `Starlette 0.47.3`
- 当前已确认 `Node.js 24.13.0` 为前端与构建运行时基线；若后续引入 Node.js 构建链路，必须补充对应版本锁定文件
- SQLite、Docker、Nginx 镜像与 cron 的精确版本必须在目标部署环境创建时记录到部署清单

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
| `/etc/bingwall/nginx` | 仓库内 Docker `nginx` 备用方案的配置目录 |

### 目录权限建议

为满足“应用写入、Nginx 读取”的最小要求，建议按以下方式创建目录：

- `/opt/bingwall/app`：代码目录，建议 `bingwall:bingwall`
- `/var/lib/bingwall/data`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/tmp`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/failed`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/public`：应用写入、Nginx 读取，建议 `2750`，`bingwall:www-data`
- `/var/log/bingwall`：应用日志和 Nginx 日志目录，建议 `0750`
- `/etc/bingwall`：受控配置目录，建议 `0750`，仅运维与应用账户可访问
- `/etc/bingwall/nginx`：仅在使用仓库内 Docker `nginx` 备用方案时创建，建议 `0750`

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
| 告警配置 | 当前未提供内建发送器；若使用 Server 酱，可通过 `BINGWALL_ALERT_SERVERCHAN_SENDKEY` 在受控环境文件中注入密钥 |

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

- 以下阈值用于当前阶段的最小运维告警方案；仓库内仍未提供邮件、Webhook 或其他主动告警发送能力，发送动作需由目标机外层监控或巡检脚本承担
- 当前代码里唯一直接内建的阈值是深度健康检查中的磁盘使用率 `85%`
- 最小必配：
  - 最近 `3` 个 `trigger_type = cron` 且 `task_type = scheduled_collect` 的任务全部为 `failed` 或 `partially_failed`
  - `GET /api/health/deep` 连续 `2` 次返回 HTTP 非 `200`，或返回体中的 `status != ok`
  - `disk_usage.used_percent >= 85%`
  - 最近一次成功备份距当前超过 `30` 小时
- 可后续补充：
  - 最近 `50` 次下载中失败率超过 `20%`
  - 最近 `5` 分钟 API `5xx` 比例超过 `5%`

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
| `BINGWALL_APP_HOST` | `127.0.0.1` | FastAPI 监听地址；当前生产模板默认监听回环地址 |
| `BINGWALL_APP_PORT` | `8000` | FastAPI 监听端口；当前生产模板默认端口，本地开发示例通常使用 `30003` |
| `BINGWALL_APP_BASE_URL` | `http://127.0.0.1:30003` | 对外基础 URL，用于生成站点级链接与回调语义 |
| `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` | 未设置 | 仅当资源使用 `storage_backend = oss` 时设置；本地文件存储场景保持未设置 |
| `BINGWALL_LOG_LEVEL` | `INFO` | 当前唯一已实现的日志级别配置项 |
| `BINGWALL_ALERT_SERVERCHAN_SENDKEY` | 未设置 | 可选；仅当外层告警脚本使用 Server 酱通道时设置，建议写入 `.env` 或 `/etc/bingwall/bingwall.env`，不要写死到脚本或文档 |
| `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED` | `true` | 采集完成且资源就绪后是否自动公开；生产模板默认延续当前自动公开策略 |
| `BINGWALL_COLLECT_NASA_APOD_ENABLED` | `true` | 是否启用 `nasa_apod` 来源采集 |
| `BINGWALL_COLLECT_NASA_APOD_DEFAULT_MARKET` | `global` | `nasa_apod` 默认市场代码，当前固定使用 `global` |
| `BINGWALL_COLLECT_NASA_APOD_API_KEY` | `DEMO_KEY` | NASA APOD API 密钥；生产环境应替换为真实密钥 |
| `BINGWALL_COLLECT_NASA_APOD_TIMEOUT_SECONDS` | `10` | NASA APOD HTTP 请求超时时间 |
| `BINGWALL_COLLECT_NASA_APOD_MAX_DOWNLOAD_RETRIES` | `3` | NASA APOD 图片下载最大重试次数 |
| `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` | 未设置 | 可选；仅在首次执行 `make db-migrate` 且 `admin_users` 为空时用于创建引导管理员 |
| `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD` | 未设置 | 可选；必须与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 成对提供，且至少 `12` 位 |

补充说明：

- `BINGWALL_APP_HOST` 与 `BINGWALL_APP_PORT` 当前会被应用配置模型、`make run` 和 `deploy/systemd/bingwall-api.service` 共同使用；当前生产模板默认口径是 `127.0.0.1:8000`
- `deploy/nginx/bingwall.conf` 当前默认把 upstream 指向 `127.0.0.1:8000`；若生产环境需要改监听地址或端口，必须同步修改 `/etc/bingwall/bingwall.env` 与上游代理的转发目标；若使用仓库内 Docker `nginx` 备用方案，再同步修改实际挂载的 `bingwall.conf`
- `deploy/systemd/bingwall.env.example` 现在已与 `.env.example` 对齐，预填 `BINGWALL_COLLECT_NASA_APOD_*` 默认键；生产环境不使用该来源时，建议显式设置 `BINGWALL_COLLECT_NASA_APOD_ENABLED=false`
- `BINGWALL_COLLECT_NASA_APOD_API_KEY` 在模板中仍保留 `DEMO_KEY` 仅用于占位；真实生产环境应替换为有效 NASA API Key，或直接关闭该来源
- `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_*` 属于一次性引导配置；首次成功初始化管理员后，建议从生产环境文件中移除，降低误用与暴露风险
- `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 只在 `storage_backend = oss` 场景填写；本地文件存储场景不要写成空字符串，而应保持未设置
- `BINGWALL_ALERT_SERVERCHAN_SENDKEY` 属于敏感密钥，只应保存在本地 `.env` 或目标机 `/etc/bingwall/bingwall.env` 这类受控环境文件中，不应写死到仓库配置、脚本参数或文档正文

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
- Node 测试入口：`npm test`
- 带后台登录账号的示例模板：`scripts/dev/playwright_smoke_with_admin.example.sh`
- 默认前提：先执行 `npm ci`、`npm test`，再通过 `bash scripts/dev/run-api.sh` 或 `make run` 启动本地服务；默认本地监听口径为 `127.0.0.1:30003`
- 统一入口：`make browser-smoke`
- 等价入口：`node scripts/dev/playwright_smoke.js`、`npm run browser-smoke`
- 带后台登录账号的模板入口：`bash scripts/dev/playwright_smoke_with_admin.example.sh`
- 可选环境变量：
  - `BINGWALL_BROWSER_BASE_URL`：改写默认访问地址；未设置时优先回退到 `BINGWALL_APP_BASE_URL`
  - `BINGWALL_BROWSER_HEADLESS=false`：切换到非无头模式
  - `BINGWALL_ADMIN_USERNAME`、`BINGWALL_ADMIN_PASSWORD`：启用真实后台登录验证
- 当前脚本默认覆盖公开首页、公开列表筛选、壁纸详情页和后台登录页壳；若提供后台账号，还会继续验证后台登录跳转
- `npm ci` 会安装锁定版本的 Playwright 依赖，不需要再手工追加 `npm install --no-save playwright`
- 若当前环境跳过了浏览器下载，或本机浏览器缓存已被清理，可执行 `npx playwright install chromium`
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
- 若要在新的目标机复制部署，仍需按本文件的生产步骤安装正式服务配置，并在 Nginx Proxy Manager、等价反向代理或已评估的公网端口方案中完成真实入口配置

### 生产环境最小启动步骤

1. 把仓库代码部署到 `/opt/bingwall/app`
2. 使用 `uv python install 3.14` 与 `uv sync --python 3.14 --frozen --no-dev` 准备生产虚拟环境
3. 复制 `deploy/systemd/bingwall.env.example` 到 `/etc/bingwall/bingwall.env`，替换域名、会话密钥和实际路径；仅在资源使用 `storage_backend = oss` 时设置 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL`
   若启用 NASA APOD，需把模板中的 `BINGWALL_COLLECT_NASA_APOD_API_KEY=DEMO_KEY` 替换为真实值；若不启用，则显式设置 `BINGWALL_COLLECT_NASA_APOD_ENABLED=false`
   若仅用于首次初始化管理员，可临时取消注释 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`，并在引导成功后移除
4. 使用 `set -a && source /etc/bingwall/bingwall.env && set +a` 导入环境后执行 `uv run --no-sync python -m app.repositories.migrations`
5. 安装 `deploy/systemd/bingwall-api.service` 与 `deploy/systemd/bingwall.tmpfiles.conf`
6. 执行 `systemd-tmpfiles --create`、`systemctl enable --now bingwall-api.service`
7. 选择对外入口：
   若目标机已有 Nginx Proxy Manager 或等价反向代理，则把外部访问入口转发到 `127.0.0.1:8000`
   `Scheme=http`、`Forward Hostname / IP=127.0.0.1`、`Forward Port=8000`
   若本次部署与 `H5` 当前已验收目标机一致，直接开放公网 `8000/tcp`，则需把 `BINGWALL_APP_HOST=0.0.0.0`，并同步确认云安全组 / 本机防火墙已放行 `8000/tcp`
8. 以 `bingwall` 用户执行 `make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env CRON_LOG_DIR=/var/log/bingwall`

### 生产环境模板说明

#### `deploy/systemd/bingwall-api.service`

- 通过 `/etc/bingwall/bingwall.env` 注入受控环境变量
- 使用 `bingwall` 账号运行应用
- 通过 `/usr/bin/env uv run --no-sync python ...` 统一走 `uv` 运行入口，并固定 `PATH=/usr/local/bin:/usr/bin:/bin`
- 当前模板会直接读取 `BINGWALL_APP_HOST` 与 `BINGWALL_APP_PORT`；生产默认口径是 `127.0.0.1:8000`
- 正式资源目录继续使用 `bingwall:www-data` 和 `2750`；应用依赖目录属主写入，目录上的 `setgid` 负责让新文件继承 `www-data`，供 Nginx 读取
- 采用 `Restart=on-failure`，在进程异常退出后自动重启
- 当前模板已启用 `ProtectSystem=strict`，并仅通过 `ReadWritePaths=/var/lib/bingwall /var/log/bingwall /etc/bingwall` 放行数据库、图片、日志和受控配置目录写入
- 当前模板已额外启用 `RemoveIPC`、`PrivateDevices`、`ProtectClock`、`ProtectControlGroups`、`ProtectKernelLogs`、`ProtectKernelModules`、`ProtectKernelTunables`、`ProtectProc=invisible`、`ProcSubset=pid`、`RestrictNamespaces`、`RestrictSUIDSGID`、`LockPersonality`、`RestrictRealtime`、`SystemCallArchitectures=native` 与空 `CapabilityBoundingSet`，用于收紧设备、内核接口、命名空间和进程可见性
- 当前模板保留 `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`，只允许本地 socket 与常规 IPv4 / IPv6 网络访问；不要在未评估采集链路前启用 `PrivateNetwork=true`
- 以当前模板执行 `systemd-analyze security --offline=yes deploy/systemd/bingwall-api.service`，离线暴露评分基线应降到约 `2.8`；如果后续新增运行时能力，应重新评估这些沙箱约束是否仍然成立

#### 反向代理推荐口径

- 真实目标机优先复用现成的 Nginx Proxy Manager 或等价反向代理，不再额外为 BingWall 单独长驻一个 `nginx` 容器
- 推荐把 Proxy Host 转发到 `127.0.0.1:8000`
- 公开页面、后台页面、公开 API、后台 API、`/assets/*`、`/admin-assets/*` 与 `/images/*` 都继续由 `bingwall-api` 提供，反向代理只负责入口转发
- 若未来启用 HTTPS、访问控制或来源 IP 限制，应优先在现有代理层实施，而不是在应用服务模板里额外堆叠一层 `nginx`
- 当前 `H5` 已验收目标机 `139.224.235.228` 暂未复用代理层，而是直接暴露 `http://139.224.235.228:8000`；该形态可作为最小公网入口记录，但不改变仓库对“优先复用现成代理层”的推荐
- 若目标机没有现成反向代理，可再启用 [deploy/systemd/bingwall-nginx.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-nginx.service) 作为备用方案

#### `deploy/systemd/bingwall-nginx.service`（备用）

- 该模板仅在目标机没有现成反向代理、但仍希望以容器方式长驻 `nginx` 时使用
- 以系统级 `systemd` 托管 `Docker` 容器中的 `nginx:1.27-alpine`
- 固定容器名 `bingwall-nginx`，便于执行 `docker ps`、`docker logs` 与 `docker exec`
- 使用 `--network host` 暴露 `80` 端口，避免额外维护端口映射和容器内外地址转换
- 挂载 `/etc/bingwall/nginx/bingwall.conf` 作为容器内 `/etc/nginx/conf.d/default.conf`
- 挂载 `/var/lib/bingwall/images/public` 与 `/opt/bingwall/app/web/public/assets`，让代理容器直接提供图片与前端静态资源
- 通过 `Requires=docker.service bingwall-api.service` 与 `Restart=always` 保证应用服务和代理容器的启动顺序与长期驻留行为

#### `deploy/systemd/bingwall.tmpfiles.conf`

- 统一创建数据库、图片、日志、备份和配置目录
- 正式资源目录使用 `bingwall:www-data` 和 `2750`
- 临时目录、失败目录、数据库目录不对 Nginx 开放
- 仅本地文件存储时，应保持 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 未设置，不要写成空字符串
- 如启用 OSS/CDN 公网访问，需要配置 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL`，例如 `https://cdn.example.com/bingwall`
- 如需调整 Bing 手动/定时采集覆盖的地区，可在环境文件中设置 `BINGWALL_COLLECT_BING_MARKETS=zh-CN,en-US,ja-JP,en-GB,de-DE,fr-FR,en-CA,en-AU`
- 如需调整 Bing 定时采集回溯窗口，可把 `BINGWALL_COLLECT_BING_SCHEDULED_BACKTRACK_DAYS` 设为 `3`、`5` 或 `7`
- 生产模板已预填 `BINGWALL_COLLECT_NASA_APOD_*` 默认值；若继续启用该来源，应替换真实 API Key，若不需要则显式关闭
- 如需首次自动创建后台管理员，可在环境文件中取消注释 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`；`make db-migrate` 仅会在 `admin_users` 为空时创建一个启用中的 `super_admin`
- 引导管理员创建成功后，建议从生产环境文件中移除 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_*`，避免后续迁移时重复携带一次性敏感值
- 如需保留“采集后先人工审核再发布”的旧策略，可在环境文件中把 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED=false`

#### `deploy/nginx/bingwall.conf`

- 该模板主要供仓库内 Docker `nginx` 备用方案挂载到容器内的 `/etc/nginx/conf.d/default.conf`
- 默认 upstream 指向 `127.0.0.1:8000`，应与 `/etc/bingwall/bingwall.env` 中的 `BINGWALL_APP_HOST` / `BINGWALL_APP_PORT` 保持一致
- `/api/` 反向代理到该 upstream
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

当前已记录的目标机首轮闭环结果：

- `H4` 首轮 `cron` 闭环验证已根据 `2026-04-04` 目标机执行报告回写到仓库，记录文件见 [docs/h4-cron-first-run-record-2026-04-04.md](/home/ops/Projects/BingWall/docs/h4-cron-first-run-record-2026-04-04.md)
- 当前已验收目标机实际使用 `ubuntu` 用户在 `/home/ubuntu/BingWall` 直接部署，`cron` 安装路径、备份目录与仓库推荐的 `/opt/bingwall/app` 口径存在差异
- 运维执行记录模板已补充到 [docs/operations-record-templates.md](/home/ops/Projects/BingWall/docs/operations-record-templates.md)，当前生产机仍建议补齐日志轮转

### H5 已验收目标机记录

- 验收日期：`2026-04-04`
- 目标机：阿里云 Ubuntu，公网 IP `139.224.235.228`
- 当前公网入口：`http://139.224.235.228:8000`
- 当前部署形态：`systemd` 长驻 `uvicorn`，由应用直接监听公网 `8000/tcp`
- 目标机执行记录：应用状态为“运行中”，`bingwall-api.service` 为 `active` 且 `enabled`
- 本次会话外部复核结果：
  - `curl -I http://139.224.235.228:8000/` 返回 `HTTP/1.1 200 OK`
  - `curl http://139.224.235.228:8000/api/health/live` 返回 `{"status":"ok", ...}`
  - `curl http://139.224.235.228:8000/api/public/site-info` 返回 `site_name = "BingWall"`
  - `curl -I http://139.224.235.228:8000/images/bing/2026/04/03_OHR.GrouseGuff_ZH-CN2647001885_preview_1600x900.jpg` 返回 `HTTP/1.1 200 OK`
  - `curl -I http://139.224.235.228:8000/admin/login` 返回 `HTTP/1.1 200 OK`

说明：

- 上述公网访问结果已由当前会话直接复核
- `systemctl status` 与开机自启状态来自目标机部署记录，当前会话未直接登录目标机执行
- 若后续要把这台机器收敛回仓库推荐口径，可把应用监听改回 `127.0.0.1:8000`，再由 Nginx Proxy Manager 或等价反向代理接管公网入口

### H4 首轮 cron 闭环记录

- 记录日期：`2026-04-04`
- 记录来源：目标机执行报告回写；当前会话未直接登录目标机复核
- 记录文件：[docs/h4-cron-first-run-record-2026-04-04.md](/home/ops/Projects/BingWall/docs/h4-cron-first-run-record-2026-04-04.md)
- 当前目标机实际口径：
  - 应用目录：`/home/ubuntu/BingWall`
  - 服务用户：`ubuntu`
  - `uv` 路径：`/home/ubuntu/.local/bin/uv`
  - 备份目录：`/home/ubuntu/BingWall/var/backups`
  - 深度健康检查地址：`http://127.0.0.1:8000/api/health/deep`
- 验收摘要：
  - 已安装 5 条 BingWall `cron` 任务，并备份旧 `crontab` 到 `/var/log/bingwall/crontab.backup.20260404T091149Z.txt`
  - `create-scheduled-collection-tasks` 首轮成功创建 `9` 个任务，其中 `8` 个 Bing 市场任务、`1` 个 `NASA APOD` 任务
  - `consume-collection-tasks --max-tasks 5` 首轮成功处理 `5` 个任务，累计成功下载 `9` 张图片
  - `run_resource_inspection.py` 已巡检 `20` 个资源，`missing_resource_count = 0`
  - `run_wallpaper_archive.py` 成功执行，当前新部署环境无历史资源需要归档
  - `run_backup.py --skip-nginx --skip-tmpfiles` 已产出 `backup-20260404T094004Z-d0172fd9/manifest.json`
  - `curl -sS http://127.0.0.1:8000/api/health/deep` 返回 `status = healthy`

### 健康检查

当前已提供：

- `GET /api/health/live`：确认进程可响应
- `GET /api/health/ready`：确认配置、数据库和关键目录可用；失败时返回 `503`
- `GET /api/health/deep`：返回最近一次采集任务摘要、磁盘使用率和资源目录摘要；严重异常时返回 `503`
- `make inspect-resources`：巡检数据库就绪资源与正式资源目录的一致性，发现资源缺失时自动刷新资源与内容状态
- `make archive-wallpapers`：把本地 ready 资源迁移到统一结构化路径，清理临时目录遗留文件、空文件和重复孤儿文件，并把损坏资源隔离到失败目录；若发现损坏资源或目标路径存在内容冲突，命令会返回非零退出码

### 最小告警方案（M4）

#### 告警渠道决策

- 当前阶段的最小告警渠道固定为“运维值班群 Webhook”，当前已选定并实测通过的具体通道为 Server 酱（ServerChan）
- Webhook 可选任一支持 HTTP POST 的群机器人或事件入口，例如 Server 酱、飞书、企业微信、Slack 或等价平台；仓库只约定“可被 `curl` 直接测试”的接口形态，不绑定具体厂商
- 选择 Webhook 的原因是：当前仓库没有 SMTP、告警中心或消息队列依赖，而 Webhook 可直接复用目标机现有 `curl` 与 `cron` 能力完成测试和后续对接
- 当前边界仍保持不变：BingWall 仓库没有内建主动发告警能力；告警应由目标机外层 URL 监控、主机巡检脚本或现有运维平台发送

#### 推荐落地方式

- URL 监控：每 `1` 分钟访问 `http://127.0.0.1:8000/api/health/deep`；连续 `2` 次 HTTP 非 `200` 或返回 `status != ok` 时推送 Webhook
- 主机侧巡检：每 `10` 分钟检查最近 `3` 个定时采集任务状态、最近一次成功备份时间和磁盘占用；命中阈值即推送 Webhook
- 值班对象：至少落到 `1` 个运维值班群；若 `30` 分钟内无人确认，再升级到站点维护人私聊、电话或等价即时渠道

#### 触发矩阵

| 场景 | 级别 | 触发条件 | 检测入口 | 首次处理要求 | 升级路径 |
|---|---|---|---|---|---|
| 采集连续失败 | `P2` | 最近 `3` 个 `cron` 采集任务全部为 `failed` 或 `partially_failed` | SQLite `collection_tasks`、后台 `/admin/tasks` | 10 分钟内确认上游源站、网络、磁盘与任务错误摘要 | 30 分钟未恢复或连续第 `4` 次失败时升级 |
| 深度健康异常 | `P1` | `GET /api/health/deep` 连续 `2` 次 HTTP 非 `200`，或返回 `status = fail` | `/api/health/deep` | 5 分钟内确认服务进程、数据库路径、关键目录和磁盘状态 | 15 分钟未恢复时升级 |
| 深度健康降级 | `P2` | `GET /api/health/deep` 连续 `2` 次返回 `status = degraded` | `/api/health/deep` | 10 分钟内确认最近任务失败原因、资源状态和回退日志 | 30 分钟未恢复时升级 |
| 备份过期 | `P1` | 最近一次成功备份距当前超过 `30` 小时，或最新快照缺少 `manifest.json` | 备份目录、`backup.log` | 15 分钟内确认 `cron`、备份目录权限和快照完整性，并补跑一次 `make backup` | 30 分钟内仍无法生成可用快照时升级 |
| 磁盘占用过高 | `P1` | `disk_usage.used_percent >= 85%`，或 `/api/health/deep` 中任一磁盘项状态为 `fail` | `/api/health/deep`、`df -h` | 15 分钟内确认占满目录，优先处理日志、临时文件和历史备份 | 30 分钟内仍高于 `85%` 或继续上涨时升级 |

#### 推荐检查命令

最近 `3` 个 `cron` 采集任务是否全部失败：

```bash
sqlite3 /var/lib/bingwall/data/bingwall.sqlite3 "
SELECT COUNT(*)
FROM (
  SELECT task_status
  FROM collection_tasks
  WHERE trigger_type = 'cron'
    AND task_type = 'scheduled_collect'
    AND finished_at_utc IS NOT NULL
  ORDER BY created_at_utc DESC, id DESC
  LIMIT 3
)
WHERE task_status IN ('failed', 'partially_failed');
"
```

结果为 `3` 时触发“采集连续失败”告警。

检查深度健康：

```bash
curl -sS http://127.0.0.1:8000/api/health/deep
```

检查最近备份年龄：

```bash
python - <<'PY'
from pathlib import Path
import time

manifests = sorted(
    Path("/var/backups/bingwall").glob("backup-*/manifest.json"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)
if not manifests:
    print("missing")
else:
    age_hours = (time.time() - manifests[0].stat().st_mtime) / 3600
    print(f"{age_hours:.2f}")
PY
```

结果为 `missing` 或大于 `30.00` 时触发“备份过期”告警。

#### 值班处理步骤

1. 在值班群内确认告警已被接手，并记录确认时间
2. 保留第一现场信息：告警原文、`/api/health/deep` 返回、相关日志片段、执行命令和结果
3. 优先恢复服务可用性，再处理根因；禁止先删库、先清空正式资源或直接覆盖历史备份
4. 若需要人工补跑，优先使用 `make consume-collection-tasks`、`make inspect-resources`、`make archive-wallpapers`、`make backup`
5. 恢复后补一条“恢复通知”到同一值班群，并在后续运维记录中补全时间线、影响范围、处置动作和回滚点

#### Webhook 真实测试通知

- 已于 `2026-04-05T03:22:59Z` 使用 Server 酱通道完成一次真实测试通知
- 执行方式：对 Server 酱 `.send` 接口发起 `POST`，标题为 `[BingWall] M4 alert test`
- 入队回执：`code = 0`
- 状态查询结果：`wxstatus` 返回成功
- 记录边界：仓库内不保存真实 SENDKEY，仅记录“通道类型、执行时间、结果摘要”；实际密钥建议通过 `BINGWALL_ALERT_SERVERCHAN_SENDKEY` 从 `.env` 或 `/etc/bingwall/bingwall.env` 注入

建议测试命令模板如下：

```bash
curl -sS -X POST "https://sctapi.ftqq.com/${BINGWALL_ALERT_SERVERCHAN_SENDKEY}.send" \
  -H "Content-Type: application/x-www-form-urlencoded; charset=utf-8" \
  --data-urlencode "title=[BingWall] alert test" \
  --data-urlencode "desp=## BingWall alert test"
```

- 通过标准：值班群实际收到测试消息，且记录中包含执行时间、操作者、目标渠道和返回结果

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
3. 如需原位恢复，执行 `uv run --no-sync python scripts/run_restore.py --snapshot /var/backups/bingwall/<snapshot> --database-path /var/lib/bingwall/data/bingwall.sqlite3 --public-dir /var/lib/bingwall/images/public --config-dir /etc/bingwall --log-dir /var/log/bingwall --backup-dir /var/backups/bingwall --nginx-config-path <proxy-config-path> --systemd-service-path /etc/systemd/system/bingwall-api.service --tmpfiles-config-path /etc/tmpfiles.d/bingwall.conf --force`
4. 恢复完成后启动或重启应用与代理服务
5. 执行 `curl http://127.0.0.1/api/health/deep`
6. 执行 `make inspect-resources`
7. 执行 `make archive-wallpapers`
8. 验证 `curl http://127.0.0.1/`、`curl http://127.0.0.1/api/public/site-info` 和后台登录/后台列表接口

## 10. 运维执行记录模板（M5）

当前仓库已把部署、恢复演练、`cron` 首轮验证、域名切换与回滚的固定模板沉淀到 [docs/operations-record-templates.md](/home/ops/Projects/BingWall/docs/operations-record-templates.md)。

使用要求：

- 执行关键运维动作前，先复制对应模板到日期化记录文件，例如 `docs/deployment-record-2026-04-06.md`
- 至少填写时间、操作者、环境、命令、结果、风险、回滚点
- 未实际执行的步骤必须写明“未执行”或“待验证”，不要补写推测结果
- 若存在截图、工单或日志文件，应在记录末尾补充附件路径，便于后续交接和复盘

建议优先使用以下模板：

| 场景 | 模板 |
| --- | --- |
| 正式部署 / 升级 | `部署记录模板` |
| 恢复演练 / 故障恢复 | `恢复演练记录模板` |
| `cron` 首轮闭环 | `cron 首轮验证记录模板` |
| 域名切换 / 入口迁移 / 紧急回退 | `域名切换与回滚记录模板` |

参考样例：

- 已验收的 `H4` 首轮闭环记录见 [docs/h4-cron-first-run-record-2026-04-04.md](/home/ops/Projects/BingWall/docs/h4-cron-first-run-record-2026-04-04.md)
- 该样例保留了“仓库推荐口径”和“真实目标机口径”之间的差异说明，可作为后续记录的参考结构

## 11. 上线前检查清单

### 阶段一公开链路最小检查

- 配置文件已审查
- 数据目录和权限已创建
- 反向代理入口已校验
- `systemd` 服务已可启动
- 公开页面、公开 API 和静态资源可访问
- `README.md` 中存在可复制启动说明

建议按以下顺序执行并记录结果：

1. 在仓库根目录执行 `make verify-deploy`
2. 在目标机按本文件“生产环境最小启动步骤”安装正式服务
3. 在目标机确认公网入口方案已生效：若使用 Nginx Proxy Manager 或等价反向代理，则 Proxy Host 已指向 `127.0.0.1:8000`；若直接开放公网端口，则确认 `8000/tcp` 已放行且 `BINGWALL_APP_HOST=0.0.0.0`
4. 执行 `curl http://127.0.0.1/api/health/live`
5. 执行 `curl http://127.0.0.1/api/health/ready`
6. 执行 `curl http://127.0.0.1/api/health/deep`
7. 执行 `curl http://127.0.0.1/api/public/site-info`
8. 执行 `curl http://127.0.0.1/`
9. 如已有正式资源，执行 `curl -I http://127.0.0.1/images/<正式资源相对路径>`
10. 执行 `make inspect-resources`
11. 执行 `make archive-wallpapers`
12. 观察 `journalctl -u bingwall-api.service`，并确认代理访问日志或公网探测结果正常

### 完整上线检查（阶段二目标）

- 配置文件已审查
- 数据目录和权限已创建
- 日志目录和备份目录已创建
- 反向代理入口已校验
- `systemd` 服务已可启动
- cron 已加载
- 健康检查可访问
- 首次备份可执行
- 首次恢复演练可执行
- 首次手动采集已验证

## 12. 当前已知缺口

- 最小告警方案已收敛为“Webhook + 外层巡检/监控”，且已通过 Server 酱完成 1 次真实测试通知；若后续切换正式值班群或轮换密钥，需同步补运维记录
- 尚未确认生产机日志轮转策略

补充说明：

- 当前仓库已通过临时 `systemd --user` 服务和 Docker 化 `nginx` 完成 `T1.6` 自动化验收；该 Docker 代理链路主要用于模板验证与无现成代理时的备用方案
- `H5` 所需的真实目标机长期驻留部署与公网接入已在 `2026-04-04` 完成，`H4` 首轮 `cron` 闭环记录也已在同日回写到仓库；当前剩余缺口集中在日志轮转等标准化工作

这些缺口必须在阶段一和阶段二实施中逐项关闭。
