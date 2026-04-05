# BingWall

## 项目说明

BingWall 是一个围绕 Bing 壁纸构建的图片服务系统。一期目标不是做单一下载脚本，而是建设一个可持续采集、可管理、可对外服务、可扩展演进的内容系统。

当前仓库已完成阶段一、阶段二闭环，并已落地阶段三 `T3.1` 标签体系、`T3.2` 多来源采集、`T3.3` 资源派生版本、`T3.4` OSS / CDN 兼容资源定位、`T3.5` 下载统计与 `T3.6` 关键词搜索增强；核心设计以 [系统设计说明书](docs/system-design.md) 为总纲，配套文档用于约束后续实现。

## 当前状态

- 项目阶段：阶段三能力已完成，`T3.1` 至 `T3.6` 已完成；真实目标机 `139.224.235.228:8000` 已完成 `H5` 长驻部署与 `H4` 首轮 `cron` 闭环验证，`M4` 所需最小告警方案已收敛为“Webhook + 外层巡检/监控”并通过 Server 酱完成真实测试通知，`M5` 所需运维执行记录模板已补充到 [docs/operations-record-templates.md](/home/ops/Projects/BingWall/docs/operations-record-templates.md)，当前剩余运维缺口集中在日志轮转收口
- 当前代码状态：已完成最小后端工程骨架、统一配置入口、最小 FastAPI 应用、SQLite 迁移基线、数据库初始化命令、Bing 与 NASA APOD 多来源采集及资源入库主链路、公开 API 最小集与精确查询增强、基础公开前端、`T1.6` 自动化部署验收，以及 `T2.1` 管理员认证与会话控制、`T2.2` 后台内容管理 API / 页面与审计查询、`T2.3` 手动采集任务与后台观测闭环、`T2.4` 健康检查、资源巡检与本地资源归档清理闭环、`T2.5` 备份恢复与恢复演练闭环、`T3.1` 标签体系、`T3.2` 多来源采集、`T3.3` 资源派生版本、`T3.4` OSS / CDN 兼容资源定位、`T3.5` 下载登记与后台统计、`T3.6` 关键词搜索增强，以及后台“修改密码”页面与会话失效闭环；当前公开列表页保留固定 8 个地区选项与按日期查找入口，地区筛选仍使用同一个 `market_code` 字段过滤列表
- 当前文档状态：系统设计、模块说明、数据模型、API 约定、部署运行说明、运维执行记录模板、项目状态、整改清单与 `H4` 目标机执行记录已同步到当前实现
- 已确认运行时基线：`Python 3.14`、`Node.js 24.13.0`
- 已确认后端依赖基线：`FastAPI 0.118.3`，官方支持 `Python 3.14`，并兼容 `Starlette 0.47.3`

## 文档入口

- [文档总览](docs/README.md)
- [系统设计说明书](docs/system-design.md)
- [模块说明](docs/module-overview.md)
- [数据模型说明](docs/data-model.md)
- [API 约定](docs/api-conventions.md)
- [部署与运行说明](docs/deployment-runbook.md)
- [运维执行记录模板](docs/operations-record-templates.md)
- [项目状态](PROJECT_STATE.md)
- [变更记录](CHANGELOG.md)

## 实施原则

- 以 `docs/system-design.md` 为总纲。
- 一期坚持单机闭环，不引入与当前规模不匹配的复杂基础设施。
- 所有开发任务按“阶段一 / 阶段二 / 阶段三”推进，并以文档中的验收标准作为完成依据。

## GitHub 协作流程

当前仓库已补齐面向 `dev -> main` 的 GitHub 交付流程约定：

- 向 `dev` 推送代码时，GitHub Actions 会自动执行 `CI` 工作流，并按仓库现有口径运行 `uv sync --python 3.14 --frozen` 和 `make verify`
- 针对 `main` 的 PR 会再次自动执行同一套 `make verify` 校验，避免“开发分支通过、合并前回归”的情况被漏掉
- 当 `dev` 上的 `CI` 成功后，`Auto Create PR` 工作流会检查当前是否已有未关闭的 `dev -> main` PR；如果 `dev` 确实领先于 `main`，且还没有打开中的同向 PR，就自动创建一条新的合并申请；工作流会优先读取仓库 Secret `GH_PR_TOKEN` 作为建单令牌，未配置时才回退到默认 `GITHUB_TOKEN`

`main` 分支保护的目标口径如下：

- 禁止直接推送到 `main`
- 必须通过 PR 合并
- 必须通过名为 `verify` 的必需检查
- 必须至少有 `1` 次人工 Review

仓库内已提供一次性保护脚本 [scripts/github/apply_main_branch_protection.sh](/home/ops/Projects/BingWall/scripts/github/apply_main_branch_protection.sh)。当本机具备具有仓库管理权限的 `GITHUB_TOKEN` 后，可执行：

```bash
GITHUB_TOKEN=<your_token> bash scripts/github/apply_main_branch_protection.sh
```

说明：

- 该脚本会先把仓库级 GitHub Actions 工作流权限切到 `Read and write permissions`，并允许 GitHub Actions 创建或批准 PR；这是 `Auto Create PR` 真正能建单的前提
- 该脚本会把 `main` 分支配置为强制 PR、强制 `verify` 检查、强制至少 `1` 次 Review，并对管理员同样生效
- 如需让自动建单稳定使用独立令牌，请在仓库 `Settings -> Secrets and variables -> Actions` 中新增 `GH_PR_TOKEN`；该值必须通过 Secret 注入，不能直接写入 `.github/workflows/*.yml`
- 如果仓库后续更改默认校验任务名，需要同步更新工作流中的 job 名称和脚本里的必需检查上下文
- 当前已实测 `push dev` 可触发 `CI`，且 `CI` 成功后会触发 `Auto Create PR`；本轮失败原因为仓库尚未开启“允许 GitHub Actions 创建或批准 PR”，不是工作流触发条件缺失

## 运行说明

当前已确认的一期开发运行时基线如下：

- `Python 3.14`（允许 `3.14.x` 补丁版本）
- `Node.js 24.13.0`
- `FastAPI 0.118.3`（兼容当前锁定的 `Starlette 0.47.3`）

当前仓库已提供最小后端启动与验证命令。本地开发环境请先确保已安装 `uv`；如不想手工输入 `uv` 命令，也可直接执行 `make setup`，其内部现已改为调用 `uv sync --frozen`：

```bash
uv python install 3.14
uv sync --python 3.14 --frozen
cp .env.example .env
# 编辑 .env，为首次初始化填写管理员账号与密码
# 仅在启用 OSS / CDN 公网访问时设置 BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL
make db-migrate
make collect-bing COUNT=1
# 如需只抓单个地区，可显式指定 MARKET
make collect-bing MARKET=en-US COUNT=1
# 或按日期范围精确抓取，例如只抓 UTC 昨天
make collect-bing MARKET=en-US DATE_FROM=2026-04-02 DATE_TO=2026-04-02
make collect-nasa-apod MARKET=global
make create-scheduled-collection-tasks
make scheduled-collect
make consume-collection-tasks
make inspect-resources
make archive-wallpapers
make backup
make verify-backup-restore
make verify
make verify-deploy
make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env
make run
```

说明：

- 现在本地开发、`systemd` 服务模板和 `cron` 模板都统一通过 `uv` 执行 Python 命令
- 运行时统一采用 `uv run --no-sync python ...`，避免服务启动或计划任务执行时再去改动虚拟环境
- `make run` 与 `deploy/systemd/bingwall-api.service` 现在都会读取 `BINGWALL_APP_HOST` 与 `BINGWALL_APP_PORT`；生产模板默认口径是 `127.0.0.1:8000`，如需修改，必须同步调整上游代理的转发目标；若使用仓库内 Docker `nginx` 备用方案，再同步修改 `deploy/nginx/bingwall.conf` 的 upstream
- `.env.example` 与 `deploy/systemd/bingwall.env.example` 现在都已包含 `BINGWALL_COLLECT_NASA_APOD_*` 默认键；生产环境若不使用该来源，应显式把 `BINGWALL_COLLECT_NASA_APOD_ENABLED=false`，若使用则应把 `BINGWALL_COLLECT_NASA_APOD_API_KEY` 从 `DEMO_KEY` 替换为真实值

健康检查：

```bash
curl http://127.0.0.1:30003/api/health/live
curl http://127.0.0.1:30003/api/health/ready
curl http://127.0.0.1:30003/api/health/deep
```

阶段一自动化部署验收命令：

```bash
make verify-deploy
```

说明：

- 该命令会执行 `systemd` 单元离线校验、`tmpfiles` 目录模板校验、临时 `systemd --user` 服务拉起、Docker 化 `nginx` 真实代理验证，以及页面/API/图片与日志检查。
- 验收默认使用临时本地端口 `18080`，避免占用真实系统 `80` 端口，不会改写 `/etc/systemd/system` 或现有 Nginx 配置。
- 本机需要可用的 `docker`、`systemd-run`、`systemctl --user`、`systemd-analyze` 和 `systemd-tmpfiles`。
- 如需首次自动创建后台管理员，请在 `.env` 中同时设置 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 和 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`，然后执行 `make db-migrate`；该初始化只会在 `admin_users` 为空时创建一个状态为 `enabled` 的 `super_admin`。
- 新采集内容当前默认会在资源全部就绪后自动公开；如需改回“采集后待审核”，可把 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED=false`。
- 仅本地文件存储场景下，不要把 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 留空写入 `.env`；应保持该变量未设置。只有资源使用 `storage_backend = oss` 时，才填写真实公网地址。

浏览器模拟测试（Playwright）：

```bash
npm ci
npm test
bash scripts/dev/run-api.sh
make browser-smoke
```

等价命令：

```bash
node scripts/dev/playwright_smoke.js
npm run browser-smoke
```

带后台登录账号的完整模板：

```bash
bash scripts/dev/playwright_smoke_with_admin.example.sh
```

说明：

- 脚本位置：`scripts/dev/playwright_smoke.js`
- Node 测试入口：`npm test`，当前会执行 `tests/node/*.test.js`，用于校验浏览器冒烟配置解析与默认口径
- 带后台登录账号的示例模板：`scripts/dev/playwright_smoke_with_admin.example.sh`
- `bash scripts/dev/run-api.sh` 与 `make run` 现都会读取 `.env` 中的 `BINGWALL_APP_HOST` / `BINGWALL_APP_PORT`；默认本地口径仍是 `127.0.0.1:30003`
- 默认访问地址优先取 `BINGWALL_BROWSER_BASE_URL`，否则回退到 `BINGWALL_APP_BASE_URL`，再回退到 `http://127.0.0.1:30003`
- 默认以无头 Chromium 运行；如需切到非无头模式，可设置 `BINGWALL_BROWSER_HEADLESS=false`
- 冒烟步骤默认覆盖公开首页、公开列表筛选、壁纸详情页和后台登录页壳；若同时设置 `BINGWALL_ADMIN_USERNAME` 与 `BINGWALL_ADMIN_PASSWORD`，脚本会继续执行一次真实后台登录并进入 `/admin/wallpapers`
- 若不想把管理员密码直接留在命令行历史里，可复制 `scripts/dev/playwright_smoke_with_admin.example.sh` 到临时目录后再编辑
- 执行 `npm ci` 时会一并安装仓库锁定版本的 `playwright`，不需要再手工 `npm install --no-save playwright`
- 若当前环境显式跳过了 Playwright 浏览器下载，或本机浏览器缓存已被清理，可补执行 `npx playwright install chromium`
- Ubuntu 24.04 上如果浏览器启动时报 GTK 相关依赖缺失，优先安装 `libgtk-3-0t64`；旧版发行版对应包名可能是 `libgtk-3-0`

当前 `T1.1` 到 `T1.6` 已补齐内容：

- 后端目录骨架
- `.python-version` 与 `.nvmrc` 运行时版本锁定
- `.env.example` 配置示例与启动期必填校验
- `uv python install 3.14`、`uv sync --python 3.14 --frozen` 开发环境准备入口，以及等价的 `make setup` 便捷入口；本地与部署侧 Python 执行入口现已统一为 `uv run`
- `make collect-bing COUNT=1` Bing 手动采集入口；默认会按 `BINGWALL_COLLECT_BING_MARKETS` 依次抓取固定 8 个地区，也支持通过 `MARKET=en-US` 指定单个地区，或结合 `DATE_FROM` / `DATE_TO` 精确抓取最近 8 天内的指定 UTC 日期范围
- `make collect-nasa-apod MARKET=global` NASA APOD 手动采集入口
- `make create-scheduled-collection-tasks` 每日固定日期采集任务创建入口，会按当天 UTC 日期为已启用来源生成 `queued` 的 `cron` 任务；Bing 会按 `BINGWALL_COLLECT_BING_MARKETS` 为每个市场各建一条任务，并把窗口起点按 `BINGWALL_COLLECT_BING_SCHEDULED_BACKTRACK_DAYS` 回溯
- `make scheduled-collect` 本地联调便捷入口，会先创建当天固定日期采集任务，再立即消费最多 `5` 个任务
- `make consume-collection-tasks` 手动采集任务消费入口，可供 cron 调用
- `make inspect-resources` 资源巡检入口，可供 cron 调用
- `make archive-wallpapers` 本地资源归档入口，可把历史 ready 资源迁移到统一结构化路径，并清理临时、空文件和重复孤儿文件
- `make backup` 备份入口，默认面向目标机标准目录执行一致性数据库备份和目录归档
- `make restore SNAPSHOT=/var/backups/bingwall/<snapshot> TARGET_ROOT=/tmp/bingwall-restore FORCE=1` 恢复入口，适用于先恢复到隔离目录做演练
- `make verify-backup-restore` 备份恢复演练入口，会自动执行一次“备份 -> 恢复 -> 页面/API/健康检查/巡检验证”
- `make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env` 目标机 `cron` 一键安装入口，会渲染仓库内模板、备份当前用户已有 `crontab`，再安装包含采集、消费、巡检、归档和备份的完整计划任务
- 最小 FastAPI 服务和 `/api/health/live`、`/api/health/ready`、`/api/health/deep` 健康检查
- SQLite 版本化迁移基线与核心表结构
- 空库初始化与重复执行迁移能力
- Bing 元数据拉取、字段映射、双层去重、任务与明细落库、图片下载重试和资源状态联动；当前已补齐 `subtitle`、`description`、`location_text`、`published_at_utc` 与 `portrait_image_url` 落库
- 当同业务键壁纸已存在但尚未生成任何资源记录时，后续同键采集不会再被直接判定为重复，而会继续补齐资源，避免历史异常中断后留下“只有主体、没有图片资源”的半成品记录
- 当同业务键壁纸的资源记录已存在但本地正式文件丢失、大小不一致或图片内容已损坏时，后续同键采集会先清理旧资源记录并重建文件，避免数据库显示 `ready` 但实际资源已坏
- 新采集内容默认会在资源全部就绪后自动切到 `enabled + is_public=true`；如需保留人工审核，可通过 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED=false` 关闭自动公开
- `/api/public/wallpapers`、`/api/public/wallpapers/today`、`/api/public/wallpapers/random`、`/api/public/wallpapers/by-market/{market_code}`、`/api/public/wallpapers/by-date/{wallpaper_date}`、`/api/public/wallpapers/{wallpaper_id}`、`/api/public/wallpaper-filters`、`/api/public/tags`、`/api/public/site-info` 与 `/api/public/download-events` 十个公开接口；其中单条壁纸接口都会返回默认下载地址和 `download_variants` 多分辨率下载列表
- 统一公开成功响应、统一错误响应、分页结构、`trace_id` 回传与访问日志记录
- 公开可见性过滤：仅返回已启用、允许公开、资源已就绪且处于发布时间窗口内的数据；公开列表支持 `keyword`、`tag_keys`、`date_from`、`date_to` 组合查询，其中日期格式固定为 `YYYY-MM-DD`，且按 `wallpaper_date` 做包含边界的范围过滤；`/api/public/wallpapers/today` 优先返回 UTC 今天的公开壁纸，若今天没有则回退到 UTC 昨天，并在候选日期内优先默认市场，`/api/public/wallpapers/random` 仅从当前公开可见内容中随机返回，`/api/public/wallpapers/by-market/{market_code}` 返回该地区最新一张公开壁纸，`/api/public/wallpapers/by-date/{wallpaper_date}` 按指定日期精确取一张并优先默认市场
- `/` 首页、`/wallpapers` 列表页、`/wallpapers/{id}` 详情页三个公开页面；其中首页已直接展示“今日壁纸 API”和“随机壁纸 API”两个快捷入口，`/wallpapers` 提供固定 8 个地区选项与单独的日期选择器；地区筛选通过公开列表接口按 `market_code` 过滤，日期选择器调用 `/api/public/wallpapers/by-date/{wallpaper_date}` 精确查找单张公开壁纸
- `web/public/assets/site.css` 与 `web/public/assets/site.js` 页面静态资源
- 前端页面只通过公开 API 获取业务数据，并在空结果、内容不存在、服务繁忙时显示明确提示
- `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall-nginx.service`、`deploy/systemd/bingwall.tmpfiles.conf` 与 `deploy/systemd/bingwall.env.example` 单机部署模板
- `scripts/install_cron.py`、`deploy/cron/bingwall-cron` 与 `make install-cron` 目标机 `cron` 一键安装入口；模板固定使用 `CRON_TZ=UTC`，执行前会加载 `/etc/bingwall/bingwall.env`，并默认包含“建任务、消费队列、资源巡检、资源归档、备份”五类计划任务
- `scripts/verify_t1_6.py` 与 `make verify-deploy` 自动化部署验收入口
- 已在当前仓库环境通过临时 `systemd --user` 服务和 Docker 化 `nginx` 完成公开页面、公开 API、静态资源、图片访问与日志校验

当前 `T2.1` 已补齐内容：

- `/api/admin/auth/login`、`/api/admin/auth/change-password`、`/api/admin/auth/logout` 后台认证接口
- `Authorization: Bearer <session_token>` 会话鉴权约定
- `admin_sessions` 数据表与会话令牌摘要持久化
- 管理员密码摘要校验、账号状态检查、会话过期判断、主动登出失效，以及登录后自助修改密码
- 登录/登出审计日志写入与当前管理员上下文注入能力
- 修改密码成功后会立即使当前账号已有后台会话失效，要求使用新密码重新登录
- 后台鉴权集成测试、密码摘要与会话摘要单元测试

当前 `T2.2` 已补齐内容：

- `/api/admin/wallpapers`、`/api/admin/wallpapers/{wallpaper_id}`、`/api/admin/wallpapers/{wallpaper_id}/status`、`/api/admin/audit-logs` 后台接口
- 后台内容列表、详情、状态切换和审计查询 schema / repository / service；内容列表支持 `keyword + 状态` 联合检索
- 启用、禁用和逻辑删除的状态流转校验，以及每次状态变更的审计日志写入
- `/admin/login`、`/admin`、`/admin/wallpapers`、`/admin/wallpapers/{id}`、`/admin/change-password`、`/admin/audit-logs` 后台页面
- `web/admin/assets/admin.js` 与 `web/admin/assets/admin.css` 后台静态资源，页面仅通过后台 API 工作
- 后台内容管理、后台页面与公开可见性联动的集成测试

当前 `T2.3` 已补齐内容：

- `/api/admin/collection-tasks`、`/api/admin/collection-tasks/{task_id}`、`/api/admin/collection-tasks/{task_id}/consume`、`/api/admin/collection-tasks/{task_id}/retry`、`/api/admin/logs` 后台任务与结构化日志接口
- 手动采集任务创建、任务列表、任务详情、`queued` 任务人工触发执行、失败任务重试、结构化日志查询和 `collection_task_items` 明细展示
- `app.collectors.manual_tasks` 与 `make consume-collection-tasks` 队列消费入口，按 `queued -> running -> succeeded / partially_failed / failed` 更新任务状态
- `scripts/create_scheduled_collection_tasks.py` 与 `make create-scheduled-collection-tasks` 每日固定日期采集任务创建入口；Bing 会按 `BINGWALL_COLLECT_BING_MARKETS` 为每个市场分别创建 `trigger_type=cron` 的 `scheduled_collect` 任务，并把 `date_from` 按 `BINGWALL_COLLECT_BING_SCHEDULED_BACKTRACK_DAYS` 回溯到窗口起点；若同来源同市场同窗口已有 `queued` / `running` / `succeeded` / `partially_failed` 任务，则保守跳过，避免重复堆积
- `/admin/tasks`、`/admin/tasks/{task_id}`、`/admin/logs` 后台页面，以及任务创建表单、手动触发按钮、统计摘要、错误摘要和逐条处理明细展示
- 手动采集与后台观测的集成测试，覆盖任务创建、消费、日志查询、重试和前端页面壳

当前 `T2.4` 已补齐内容：

- `/api/health/ready`、`/api/health/deep` 健康检查接口，覆盖数据库、关键目录、磁盘使用率和最近一次采集任务摘要
- `scripts/run_resource_inspection.py` 与 `make inspect-resources` 资源巡检入口，可检查数据库就绪资源与正式资源目录的一致性
- `scripts/run_wallpaper_archive.py` 与 `make archive-wallpapers` 本地资源归档入口，可把历史 ready 资源迁移到 `source/year/month/day_market_type_resolution.ext` 结构化路径，同时清理临时目录遗留文件、空文件、重复孤儿文件，并把损坏资源隔离到失败目录
- 资源文件缺失后的状态联动：自动把异常资源标记为 `failed`，刷新壁纸 `resource_status`，并在公开启用内容失去可用资源时将其降级为 `disabled`
- 资源归档若发现图片内容损坏、文件大小与记录不一致，或目标结构化路径已存在不同内容文件，会返回非零退出码，便于 cron 或运维脚本及时发现异常
- 健康检查与资源巡检集成测试，覆盖 `ready` 成功/失败、`deep` 摘要返回和公开链路隔离

当前 `T2.5` 已补齐内容：

- `app/services/backup_restore.py`、`scripts/run_backup.py` 与 `scripts/run_restore.py`，支持 SQLite 一致性备份、正式资源目录归档、配置目录归档、日志归档，以及 Nginx / systemd / tmpfiles 部署配置备份和恢复
- `scripts/verify_t2_5.py` 与 `make verify-backup-restore`，支持在隔离目录执行一次完整恢复演练，并验证公开页面、公开 API、后台 API、深度健康检查和资源巡检
- `/api/health/deep` 已新增最近一次恢复验证记录摘要，便于追踪最近一次恢复演练是否通过
- 备份产物会生成 `manifest.json` 与独立 `backup.log`；恢复过程会生成独立 `restore.log`、恢复记录和恢复验证记录

当前 `T3.1` 已补齐内容：

- `app/repositories/migrations/versions/V0003__tags.sql`，落地 `tags` 与 `wallpaper_tags` 两张标签相关表和索引
- `/api/public/tags`、公开列表 `tag_keys` 标签筛选参数，以及公开筛选项中的标签输出
- `/api/admin/tags`、`/api/admin/tags/{tag_id}` 与 `/api/admin/wallpapers/{wallpaper_id}/tags` 后台接口
- `/admin/tags` 标签管理页，以及 `/admin/wallpapers/{id}` 内容详情页中的标签绑定入口
- 标签创建、更新、绑定的审计日志写入，以及多标签绑定、停用标签隐藏和公开筛选联动测试

当前 `T3.2` 已补齐内容：

- `app/services/source_collection.py`、`app/domain/collection_sources.py` 与 `app/repositories/collection_repository.py`，把采集执行链路抽象为按 `source_type` 分发的统一来源接口，并支持跨来源任务认领与结果落库
- `app/collectors/nasa_apod.py`、新增 `BINGWALL_COLLECT_NASA_APOD_*` 配置项与 `make collect-nasa-apod`，接入 `nasa_apod` 作为 Bing 之外的新来源
- 后台任务创建、重试、消费与页面筛选已支持 `bing` / `nasa_apod` 两种来源，其中 `nasa_apod` 的 `market_code` 固定为 `global`
- 已补齐多来源采集集成测试，验证 Bing 链路不回归、NASA APOD 新来源可入库、后台任务和结构化日志可按来源区分

当前 `T3.3` 已补齐内容：

- `app/services/image_variants.py`、`app/domain/resource_variants.py` 与 `V0004__image_resource_variants.sql`，把资源类型规范扩展为 `original` / `thumbnail` / `preview` / `download`
- 采集主链路在原图入库后生成缩略图、详情预览图和下载图；其中 Bing 来源现会把同一壁纸按当前约定的 5 种分辨率分别保存为多条 `download` 资源：`UHD`、`1920x1200`、`1920x1080`、`1366x768`、`720x1280`；公开列表默认使用缩略图，公开详情区分预览图、默认下载图和多分辨率下载列表
- 资源状态联动与资源巡检已按多版本资源完整性统一判断，并保留对历史仅原图数据的保守回退

当前 `T3.4` 已补齐内容：

- 新增 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 配置项和统一资源定位器，公开接口与后台接口不再把资源 URL 生成为固定的本地 `/images/...` 形式
- 当资源记录的 `storage_backend = local` 时，接口仍返回 `/images/<relative_path>`；当 `storage_backend = oss` 时，接口返回配置好的 OSS / CDN 公网地址
- 已补齐本地与 OSS 并存测试，确保迁移期间旧本地资源继续可访问，且公开接口不暴露服务器磁盘路径

当前 `T3.5` 已补齐内容：

- `V0005__download_events.sql`、`app/repositories/download_repository.py` 与 `app/services/downloads.py`，落地下载登记表、下载跳转目标解析、降级日志和后台统计聚合
- `/api/public/download-events` 公开下载登记接口，以及 `/api/admin/download-stats` 后台统计接口；公开详情页下载按钮已改为“先登记、再跳转静态资源”
- `/admin/download-stats` 后台页面，支持查看最近 7 / 30 / 90 天下载总量、热门内容和按日趋势

当前 `T3.6` 已补齐内容：

- `/api/public/wallpapers` 新增 `keyword`、`date_from`、`date_to` 查询参数，当前匹配标题、简述、版权说明、描述和启用标签，且可与 `market_code`、`tag_keys`、分辨率条件组合使用；日期范围基于 `wallpaper_date`，格式固定为 `YYYY-MM-DD`
- 已新增 `/api/public/wallpapers/by-market/{market_code}` 与 `/api/public/wallpapers/by-date/{wallpaper_date}` 两个公开单条查询接口，分别用于按地区获取最新可见壁纸、按日期精确获取单条可见壁纸；两者都返回与公开详情一致的完整结构，包含 `download_variants` 全部分辨率下载链接
- `/api/admin/wallpapers` 新增 `keyword` 查询参数，支持与 `content_status`、`image_status`、地区和创建时间联合检索，便于解释公开端和后台端结果差异
- `/wallpapers` 与 `/admin/wallpapers` 页面已新增关键词输入框，并继续只通过现有公开 / 后台 API 取数；其中公开列表页保留固定 8 个地区选项，直接通过 `/api/public/wallpapers?market_code=...` 过滤分页列表，同时新增日期选择器，单独调用 `/api/public/wallpapers/by-date/{wallpaper_date}` 精确查找当天公开壁纸
- 已补齐关键词搜索集成测试、前后台页面资产断言与代表性样本响应时间验证；当前本地样本中公开搜索约 `0.0043` 秒、后台搜索约 `0.0058` 秒

公开 API 最小验证示例：

```bash
curl http://127.0.0.1:30003/api/public/site-info
curl "http://127.0.0.1:30003/api/public/wallpapers?page=1&page_size=20&sort=date_desc"
curl "http://127.0.0.1:30003/api/public/wallpapers?page=1&page_size=20&sort=date_desc&keyword=forest"
curl "http://127.0.0.1:30003/api/public/wallpapers?page=1&page_size=20&sort=date_desc&tag_keys=theme_forest,location_asia"
curl "http://127.0.0.1:30003/api/public/wallpapers?page=1&page_size=20&sort=date_desc&date_from=2026-03-20&date_to=2026-03-24"
curl http://127.0.0.1:30003/api/public/wallpapers/today
curl http://127.0.0.1:30003/api/public/wallpapers/random
curl http://127.0.0.1:30003/api/public/wallpapers/by-market/en-US
curl http://127.0.0.1:30003/api/public/wallpapers/by-date/2026-03-24
curl http://127.0.0.1:30003/api/public/wallpaper-filters
curl http://127.0.0.1:30003/api/public/tags
curl http://127.0.0.1:30003/api/public/wallpapers/1
curl -X POST http://127.0.0.1:30003/api/public/download-events \
  -H 'Content-Type: application/json' \
  -d '{"wallpaper_id":1,"download_channel":"public_detail"}'
curl -X POST http://127.0.0.1:30003/api/public/download-events \
  -H 'Content-Type: application/json' \
  -d '{"wallpaper_id":1,"resource_id":101,"download_channel":"public_detail"}'
```

公开前端最小验证示例：

```bash
curl http://127.0.0.1:30003/
curl "http://127.0.0.1:30003/wallpapers?page=1&market_code=en-US&keyword=forest"
curl http://127.0.0.1:30003/wallpapers/1
```

说明：

- 访问 `/wallpapers` 后，可直接使用“地区”下拉按 `market_code` 过滤公开列表；当前固定提供 `zh-CN`、`en-US`、`ja-JP`、`en-GB`、`de-DE`、`fr-FR`、`en-CA`、`en-AU` 八个选项。
- 页面同时会显示“按日期查找壁纸”区域；选择日期并提交后，前端会调用 `/api/public/wallpapers/by-date/{wallpaper_date}`，只刷新该日期结果卡片，不改变下方分页列表的筛选语义。

后台鉴权最小验证示例：

```bash
curl -X POST http://127.0.0.1:30003/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"your-password"}'

curl -X POST http://127.0.0.1:30003/api/admin/auth/change-password \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"current_password":"your-password","new_password":"your-new-password","confirm_new_password":"your-new-password"}'

curl -X POST http://127.0.0.1:30003/api/admin/auth/logout \
  -H 'Authorization: Bearer <session_token>'
```

后台内容管理最小验证示例：

```bash
curl http://127.0.0.1:30003/admin/login
curl http://127.0.0.1:30003/admin/change-password
curl "http://127.0.0.1:30003/admin/wallpapers?keyword=forest"
curl http://127.0.0.1:30003/admin/tags
curl -H 'Authorization: Bearer <session_token>' \
  "http://127.0.0.1:30003/api/admin/wallpapers?content_status=draft&page=1&page_size=20&keyword=forest"
curl -H 'Authorization: Bearer <session_token>' \
  http://127.0.0.1:30003/api/admin/wallpapers/1
curl -X POST http://127.0.0.1:30003/api/admin/wallpapers/1/status \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"target_status":"enabled","operator_reason":"人工审核通过"}'
curl -H 'Authorization: Bearer <session_token>' \
  "http://127.0.0.1:30003/api/admin/audit-logs?target_type=wallpaper&target_id=1"
curl -H 'Authorization: Bearer <session_token>' \
  http://127.0.0.1:30003/api/admin/tags
curl -X POST http://127.0.0.1:30003/api/admin/tags \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"tag_key":"theme_forest","tag_name":"森林","tag_category":"theme","status":"enabled","sort_weight":10,"operator_reason":"新增公开标签"}'
curl -X PUT http://127.0.0.1:30003/api/admin/wallpapers/1/tags \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"tag_ids":[1,2],"operator_reason":"补充内容标签"}'
```

后台任务观测最小验证示例：

```bash
curl http://127.0.0.1:30003/admin/tasks
curl http://127.0.0.1:30003/admin/logs?task_id=1
curl -X POST http://127.0.0.1:30003/api/admin/collection-tasks \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"bing","market_code":"en-US","date_from":"2026-03-24","date_to":"2026-03-24","force_refresh":false}'
curl -X POST http://127.0.0.1:30003/api/admin/collection-tasks \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"nasa_apod","market_code":"global","date_from":"2026-03-24","date_to":"2026-03-24","force_refresh":false}'
curl -X POST -H 'Authorization: Bearer <session_token>' \
  http://127.0.0.1:30003/api/admin/collection-tasks/1/consume
make create-scheduled-collection-tasks
make scheduled-collect
make consume-collection-tasks
curl -H 'Authorization: Bearer <session_token>' \
  http://127.0.0.1:30003/api/admin/collection-tasks/1
curl -H 'Authorization: Bearer <session_token>' \
  "http://127.0.0.1:30003/api/admin/logs?task_id=1&error_type=failed"
```

定时采集最小验证示例：

```bash
make create-scheduled-collection-tasks
make consume-collection-tasks
cat deploy/cron/bingwall-cron
sudo -u bingwall make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env
```

说明：

- 新增的定时建任务脚本固定按 UTC 当天生成任务快照；其中 Bing 会按照 `BINGWALL_COLLECT_BING_MARKETS` 逐个市场建任务，并把 `date_to` 固定为当天、`date_from` 按 `BINGWALL_COLLECT_BING_SCHEDULED_BACKTRACK_DAYS` 回溯。
- cron 消费固定日期任务时，若上游在当天 UTC 边界尚未提供该日期图片，系统会在最近 `8` 天窗口内自动回退到最近可用日期，并写入 `resolve_date_fallback` 任务日志；手动任务仍保持严格日期匹配，不会自动放宽。
- Bing 定时任务会把 `count` 与 `backtrack_days` 一并写入任务快照，当前允许值为 `3`、`5`、`7`；任务消费时会先拉取该窗口内的元数据，再优先匹配固定日期，若当天无图，则回退到窗口内最近可用日期。
- NASA APOD 定时任务仍写入 `count=1`，但消费阶段会把上游查询窗口扩展到最近 `8` 天，并在当天无图时回退到最近可用日期。
- `deploy/cron/bingwall-cron` 现在会固定写入 `CRON_TZ=UTC`，并在每条命令前显式加载 `BINGWALL` 生产环境文件，避免 `cron` 与 `systemd` 使用不同配置来源。
- `make install-cron` 会默认安装 5 条计划任务：每日建任务、每分钟消费队列、每日资源巡检、每日资源归档、每日一致性备份；安装前会先把当前用户已有 `crontab` 备份到日志目录中的时间戳文件，便于回滚。
- 生产环境应以 `bingwall` 用户执行 `make install-cron`；当前目标机推荐命令是 `sudo -u bingwall make install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env CRON_LOG_DIR=/var/log/bingwall`。

下载统计最小验证示例：

```bash
curl http://127.0.0.1:30003/admin/download-stats
curl -H 'Authorization: Bearer <session_token>' \
  "http://127.0.0.1:30003/api/admin/download-stats?days=7&top_limit=5"
```

健康检查与资源巡检最小验证示例：

```bash
curl http://127.0.0.1:30003/api/health/live
curl http://127.0.0.1:30003/api/health/ready
curl http://127.0.0.1:30003/api/health/deep
make inspect-resources
```

备份恢复最小验证示例：

```bash
make backup
make restore SNAPSHOT=/var/backups/bingwall/backup-20260325T142430Z-xxxx TARGET_ROOT=/tmp/bingwall-restore FORCE=1
make verify-backup-restore
```

当前仍需补强：

- 日志轮转方案

## 阶段一单机部署说明

以下命令用于把当前仓库部署到单机 Ubuntu 环境，目标是让公开页面、公开 API 和图片静态资源稳定对外访问。仓库仍优先推荐复用 Nginx Proxy Manager 或等价反向代理；当前 `H5` 已验收目标机也记录了直接开放 `http://139.224.235.228:8000` 的最小公网入口。命令假定部署目录遵循 `docs/deployment-runbook.md` 中的一期约定，且部署账号具有 `sudo` 权限。

在执行真实部署前，建议先在仓库根目录执行一次 `make verify-deploy`，确认模板、代理链路和最小日志观察口径都正常。

### 1. 准备系统用户、目录和代码

```bash
sudo useradd --system --home-dir /opt/bingwall --shell /usr/sbin/nologin bingwall 2>/dev/null || true
sudo install -d -o root -g root -m 0755 /opt/bingwall
sudo rsync -a --delete --exclude '.git' ./ /opt/bingwall/app/
sudo chown -R bingwall:bingwall /opt/bingwall/app
sudo install -d -o bingwall -g bingwall -m 0750 /var/lib/bingwall/data
sudo install -d -o bingwall -g bingwall -m 0750 /var/lib/bingwall/images/tmp
sudo install -d -o bingwall -g www-data -m 2750 /var/lib/bingwall/images/public
sudo install -d -o bingwall -g bingwall -m 0750 /var/lib/bingwall/images/failed
sudo install -d -o bingwall -g bingwall -m 0750 /var/log/bingwall
sudo install -d -o bingwall -g bingwall -m 0750 /var/backups/bingwall
sudo install -d -o bingwall -g bingwall -m 0750 /etc/bingwall
```

说明：

- 应用进程使用 `bingwall` 账号运行。
- `/var/lib/bingwall/images/public` 目录使用 `bingwall:www-data` 和 `2750` 权限，应用可写入，Nginx Proxy Manager 转发后的访问仍由应用统一处理。
- 临时目录、失败目录、数据库目录和配置目录不暴露给 Nginx。

### 2. 安装 Python 依赖并初始化配置

```bash
sudo -u bingwall bash -lc 'cd /opt/bingwall/app && uv python install 3.14'
sudo -u bingwall bash -lc 'cd /opt/bingwall/app && uv sync --python 3.14 --frozen --no-dev'
sudo install -o bingwall -g bingwall -m 0640 /opt/bingwall/app/deploy/systemd/bingwall.env.example /etc/bingwall/bingwall.env
sudoedit /etc/bingwall/bingwall.env
```

修改 `/etc/bingwall/bingwall.env` 时至少需要确认：

- `BINGWALL_APP_BASE_URL` 改成实际访问域名或 IP
- `BINGWALL_SECURITY_SESSION_SECRET` 改成不少于 `32` 字节的随机值
- 如需首次自动创建后台管理员，同时填写 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`，其中密码至少 `12` 位
- 生产模板默认使用 `BINGWALL_APP_HOST=127.0.0.1` 与 `BINGWALL_APP_PORT=8000`；如需调整监听地址或端口，需要同步更新 Nginx Proxy Manager 中的转发目标
- 若当前目标机直接开放公网 `8000/tcp`，则需要把 `BINGWALL_APP_HOST=0.0.0.0`，并同步确认云安全组 / 防火墙已放行 `8000/tcp`

### 3. 初始化数据库并安装服务配置

```bash
sudo -u bingwall bash -lc 'set -a && source /etc/bingwall/bingwall.env && set +a && cd /opt/bingwall/app && uv run --no-sync python -m app.repositories.migrations'
sudo install -o root -g root -m 0644 /opt/bingwall/app/deploy/systemd/bingwall-api.service /etc/systemd/system/bingwall-api.service
sudo install -o root -g root -m 0644 /opt/bingwall/app/deploy/systemd/bingwall.tmpfiles.conf /etc/tmpfiles.d/bingwall.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/bingwall.conf
sudo systemctl daemon-reload
sudo systemctl enable --now bingwall-api.service
sudo -u bingwall make -C /opt/bingwall/app install-cron CRON_APP_DIR=/opt/bingwall/app CRON_ENV_FILE=/etc/bingwall/bingwall.env CRON_LOG_DIR=/var/log/bingwall
```

说明：

- 当 `admin_users` 为空且已配置 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME`、`BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD` 时，以上数据库初始化命令会自动创建一个状态为 `enabled` 的 `super_admin`。
- 若数据库里已经存在管理员账号，再次执行该命令不会覆盖已有账号，也不会重复创建默认管理员。
- 上述 `make install-cron` 会把仓库中的 cron 模板渲染成真实路径，并安装到 `bingwall` 用户自己的 `crontab`；如需回滚，可使用安装输出中的备份文件重新执行 `crontab <backup_path>`。
- 当前已验收目标机的等价执行记录见 [docs/h4-cron-first-run-record-2026-04-04.md](/home/ops/Projects/BingWall/docs/h4-cron-first-run-record-2026-04-04.md)；该机器实际使用 `ubuntu` 用户在 `/home/ubuntu/BingWall` 直接部署。
- 若使用现成代理层，在 Nginx Proxy Manager 中新增一个 Proxy Host，把外部访问入口转发到 `127.0.0.1:8000`；`Scheme=http`、`Forward Hostname / IP=127.0.0.1`、`Forward Port=8000`。
- 若直接开放公网 `8000/tcp`，则无需额外代理，但必须同步收紧安全组 / 防火墙与运维访问面。
- 如果目标机没有现成反向代理，再考虑使用 [deploy/systemd/bingwall-nginx.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-nginx.service) 作为备用方案。

### 4. 最小上线检查

```bash
curl http://127.0.0.1/api/health/live
curl http://127.0.0.1/api/health/ready
curl http://127.0.0.1/api/health/deep
curl http://127.0.0.1/api/public/site-info
curl http://127.0.0.1/
journalctl -u bingwall-api.service -n 50 --no-pager
```

如果前面已经执行过 Bing 采集并生成正式图片资源，还应额外检查：

```bash
curl -I http://127.0.0.1/images/<正式资源相对路径>
```

仓库已提供的生产部署模板文件：

- [deploy/nginx/bingwall.conf](/home/ops/Projects/BingWall/deploy/nginx/bingwall.conf)
- [deploy/systemd/bingwall-nginx.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-nginx.service)
- [deploy/systemd/bingwall-api.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-api.service)
- [deploy/systemd/bingwall.tmpfiles.conf](/home/ops/Projects/BingWall/deploy/systemd/bingwall.tmpfiles.conf)
- [deploy/systemd/bingwall.env.example](/home/ops/Projects/BingWall/deploy/systemd/bingwall.env.example)
