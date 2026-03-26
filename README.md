# BingWall

## 项目说明

BingWall 是一个围绕 Bing 壁纸构建的图片服务系统。一期目标不是做单一下载脚本，而是建设一个可持续采集、可管理、可对外服务、可扩展演进的内容系统。

当前仓库已完成阶段一、阶段二闭环，并已落地阶段三 `T3.1` 标签体系与 `T3.2` 多来源采集；核心设计以 [系统设计说明书](docs/system-design.md) 为总纲，配套文档用于约束后续实现。

## 当前状态

- 项目阶段：阶段三进行中，`T3.1` 与 `T3.2` 已完成；运维侧仍需补齐目标机 `cron` 安装与计划配置
- 当前代码状态：已完成最小后端工程骨架、统一配置入口、最小 FastAPI 应用、SQLite 迁移基线、数据库初始化命令、Bing 与 NASA APOD 多来源采集及资源入库主链路、公开 API 最小集、基础公开前端、`T1.6` 自动化部署验收，以及 `T2.1` 管理员认证与会话控制、`T2.2` 后台内容管理 API / 页面与审计查询、`T2.3` 手动采集任务与后台观测闭环、`T2.4` 健康检查与资源巡检闭环、`T2.5` 备份恢复与恢复演练闭环、`T3.1` 标签体系、`T3.2` 多来源采集
- 当前文档状态：系统设计、模块说明、数据模型、API 约定、部署运行说明、项目状态与阶段 TODO 已同步到当前实现
- 已确认运行时基线：`Python 3.14.2`、`Node.js 24.13.0`

## 文档入口

- [文档总览](docs/README.md)
- [系统设计说明书](docs/system-design.md)
- [模块说明](docs/module-overview.md)
- [数据模型说明](docs/data-model.md)
- [API 约定](docs/api-conventions.md)
- [部署与运行说明](docs/deployment-runbook.md)
- [阶段 TODO 路线图](docs/TODO.md)
- [项目状态](PROJECT_STATE.md)
- [变更记录](CHANGELOG.md)

## 实施原则

- 以 `docs/system-design.md` 为总纲。
- 一期坚持单机闭环，不引入与当前规模不匹配的复杂基础设施。
- 所有开发任务按“阶段一 / 阶段二 / 阶段三”推进，并以文档中的验收标准作为完成依据。

## 运行说明

当前已确认的一期开发运行时基线如下：

- `Python 3.14.2`
- `Node.js 24.13.0`

当前仓库已提供最小后端启动与验证命令：

```bash
make setup
cp .env.example .env
make db-migrate
make collect-bing MARKET=en-US COUNT=1
make collect-nasa-apod MARKET=global
make consume-collection-tasks
make inspect-resources
make backup
make verify-backup-restore
make verify
make verify-deploy
make run
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health/live
curl http://127.0.0.1:8000/api/health/ready
curl http://127.0.0.1:8000/api/health/deep
```

阶段一自动化部署验收命令：

```bash
make verify-deploy
```

说明：

- 该命令会执行 `systemd` 单元离线校验、`tmpfiles` 目录模板校验、临时 `systemd --user` 服务拉起、Docker 化 `nginx` 真实代理验证，以及页面/API/图片与日志检查。
- 验收默认使用临时本地端口 `18080`，避免占用真实系统 `80` 端口，不会改写 `/etc/systemd/system` 或现有 Nginx 配置。
- 本机需要可用的 `docker`、`systemd-run`、`systemctl --user`、`systemd-analyze` 和 `systemd-tmpfiles`。

当前 `T1.1` 到 `T1.6` 已补齐内容：

- 后端目录骨架
- `.python-version` 与 `.nvmrc` 运行时版本锁定
- `.env.example` 配置示例与启动期必填校验
- `make setup`、`make db-migrate`、`make verify`、`make run` 统一命令入口
- `make collect-bing MARKET=en-US COUNT=1` Bing 手动采集入口
- `make collect-nasa-apod MARKET=global` NASA APOD 手动采集入口
- `make consume-collection-tasks` 手动采集任务消费入口，可供 cron 调用
- `make inspect-resources` 资源巡检入口，可供 cron 调用
- `make backup` 备份入口，默认面向目标机标准目录执行一致性数据库备份和目录归档
- `make restore SNAPSHOT=/var/backups/bingwall/<snapshot> TARGET_ROOT=/tmp/bingwall-restore FORCE=1` 恢复入口，适用于先恢复到隔离目录做演练
- `make verify-backup-restore` 备份恢复演练入口，会自动执行一次“备份 -> 恢复 -> 页面/API/健康检查/巡检验证”
- 最小 FastAPI 服务和 `/api/health/live`、`/api/health/ready`、`/api/health/deep` 健康检查
- SQLite 版本化迁移基线与核心表结构
- 空库初始化与重复执行迁移能力
- Bing 元数据拉取、字段映射、双层去重、任务与明细落库、图片下载重试和资源状态联动
- `/api/public/wallpapers`、`/api/public/wallpapers/{wallpaper_id}`、`/api/public/wallpaper-filters`、`/api/public/tags`、`/api/public/site-info` 五个公开接口
- 统一公开成功响应、统一错误响应、分页结构、`trace_id` 回传与访问日志记录
- 公开可见性过滤：仅返回已启用、允许公开、资源已就绪且处于发布时间窗口内的数据
- `/` 首页、`/wallpapers` 列表页、`/wallpapers/{id}` 详情页三个公开页面
- `web/public/assets/site.css` 与 `web/public/assets/site.js` 页面静态资源
- 前端页面只通过公开 API 获取业务数据，并在空结果、内容不存在、服务繁忙时显示明确提示
- `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 与 `deploy/systemd/bingwall.env.example` 单机部署模板
- `scripts/verify_t1_6.py` 与 `make verify-deploy` 自动化部署验收入口
- 已在当前仓库环境通过临时 `systemd --user` 服务和 Docker 化 `nginx` 完成公开页面、公开 API、静态资源、图片访问与日志校验

当前 `T2.1` 已补齐内容：

- `/api/admin/auth/login`、`/api/admin/auth/logout` 后台认证接口
- `Authorization: Bearer <session_token>` 会话鉴权约定
- `admin_sessions` 数据表与会话令牌摘要持久化
- 管理员密码摘要校验、账号状态检查、会话过期判断与主动登出失效
- 登录/登出审计日志写入与当前管理员上下文注入能力
- 后台鉴权集成测试、密码摘要与会话摘要单元测试

当前 `T2.2` 已补齐内容：

- `/api/admin/wallpapers`、`/api/admin/wallpapers/{wallpaper_id}`、`/api/admin/wallpapers/{wallpaper_id}/status`、`/api/admin/audit-logs` 后台接口
- 后台内容列表、详情、状态切换和审计查询 schema / repository / service
- 启用、禁用和逻辑删除的状态流转校验，以及每次状态变更的审计日志写入
- `/admin/login`、`/admin`、`/admin/wallpapers/{id}`、`/admin/audit-logs` 后台页面
- `web/admin/assets/admin.js` 与 `web/admin/assets/admin.css` 后台静态资源，页面仅通过后台 API 工作
- 后台内容管理、后台页面与公开可见性联动的集成测试

当前 `T2.3` 已补齐内容：

- `/api/admin/collection-tasks`、`/api/admin/collection-tasks/{task_id}`、`/api/admin/collection-tasks/{task_id}/retry`、`/api/admin/logs` 后台任务与结构化日志接口
- 手动采集任务创建、任务列表、任务详情、失败任务重试、结构化日志查询和 `collection_task_items` 明细展示
- `app.collectors.manual_tasks` 与 `make consume-collection-tasks` 队列消费入口，按 `queued -> running -> succeeded / partially_failed / failed` 更新任务状态
- `/admin/tasks`、`/admin/tasks/{task_id}`、`/admin/logs` 后台页面，以及任务创建表单、统计摘要、错误摘要和逐条处理明细展示
- 手动采集与后台观测的集成测试，覆盖任务创建、消费、日志查询、重试和前端页面壳

当前 `T2.4` 已补齐内容：

- `/api/health/ready`、`/api/health/deep` 健康检查接口，覆盖数据库、关键目录、磁盘使用率和最近一次采集任务摘要
- `scripts/run_resource_inspection.py` 与 `make inspect-resources` 资源巡检入口，可检查数据库就绪资源与正式资源目录的一致性
- 资源文件缺失后的状态联动：自动把异常资源标记为 `failed`，刷新壁纸 `resource_status`，并在公开启用内容失去可用资源时将其降级为 `disabled`
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

公开 API 最小验证示例：

```bash
curl http://127.0.0.1:8000/api/public/site-info
curl "http://127.0.0.1:8000/api/public/wallpapers?page=1&page_size=20&sort=date_desc"
curl "http://127.0.0.1:8000/api/public/wallpapers?page=1&page_size=20&sort=date_desc&tag_keys=theme_forest,location_asia"
curl http://127.0.0.1:8000/api/public/wallpaper-filters
curl http://127.0.0.1:8000/api/public/tags
curl http://127.0.0.1:8000/api/public/wallpapers/1
```

公开前端最小验证示例：

```bash
curl http://127.0.0.1:8000/
curl "http://127.0.0.1:8000/wallpapers?page=1&market_code=en-US"
curl http://127.0.0.1:8000/wallpapers/1
```

后台鉴权最小验证示例：

```bash
curl -X POST http://127.0.0.1:8000/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"your-password"}'

curl -X POST http://127.0.0.1:8000/api/admin/auth/logout \
  -H 'Authorization: Bearer <session_token>'
```

后台内容管理最小验证示例：

```bash
curl http://127.0.0.1:8000/admin/login
curl http://127.0.0.1:8000/admin/wallpapers
curl http://127.0.0.1:8000/admin/tags
curl -H 'Authorization: Bearer <session_token>' \
  "http://127.0.0.1:8000/api/admin/wallpapers?content_status=draft&page=1&page_size=20"
curl -H 'Authorization: Bearer <session_token>' \
  http://127.0.0.1:8000/api/admin/wallpapers/1
curl -X POST http://127.0.0.1:8000/api/admin/wallpapers/1/status \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"target_status":"enabled","operator_reason":"人工审核通过"}'
curl -H 'Authorization: Bearer <session_token>' \
  "http://127.0.0.1:8000/api/admin/audit-logs?target_type=wallpaper&target_id=1"
curl -H 'Authorization: Bearer <session_token>' \
  http://127.0.0.1:8000/api/admin/tags
curl -X POST http://127.0.0.1:8000/api/admin/tags \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"tag_key":"theme_forest","tag_name":"森林","tag_category":"theme","status":"enabled","sort_weight":10,"operator_reason":"新增公开标签"}'
curl -X PUT http://127.0.0.1:8000/api/admin/wallpapers/1/tags \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"tag_ids":[1,2],"operator_reason":"补充内容标签"}'
```

后台任务观测最小验证示例：

```bash
curl http://127.0.0.1:8000/admin/tasks
curl http://127.0.0.1:8000/admin/logs?task_id=1
curl -X POST http://127.0.0.1:8000/api/admin/collection-tasks \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"bing","market_code":"en-US","date_from":"2026-03-24","date_to":"2026-03-24","force_refresh":false}'
curl -X POST http://127.0.0.1:8000/api/admin/collection-tasks \
  -H 'Authorization: Bearer <session_token>' \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"nasa_apod","market_code":"global","date_from":"2026-03-24","date_to":"2026-03-24","force_refresh":false}'
make consume-collection-tasks
curl -H 'Authorization: Bearer <session_token>' \
  http://127.0.0.1:8000/api/admin/collection-tasks/1
curl -H 'Authorization: Bearer <session_token>' \
  "http://127.0.0.1:8000/api/admin/logs?task_id=1&error_type=failed"
```

健康检查与资源巡检最小验证示例：

```bash
curl http://127.0.0.1:8000/api/health/live
curl http://127.0.0.1:8000/api/health/ready
curl http://127.0.0.1:8000/api/health/deep
make inspect-resources
```

备份恢复最小验证示例：

```bash
make backup
make restore SNAPSHOT=/var/backups/bingwall/backup-20260325T142430Z-xxxx TARGET_ROOT=/tmp/bingwall-restore FORCE=1
make verify-backup-restore
```

当前仍未补齐：

- 目标机 cron 安装与计划配置

## 阶段一单机部署说明

以下命令用于把当前仓库部署到单机 Ubuntu 环境，目标是让公开页面、公开 API 和图片静态资源都通过 Nginx 对外访问。命令假定部署目录遵循 `docs/deployment-runbook.md` 中的一期约定，且部署账号具有 `sudo` 权限。

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
- `/var/lib/bingwall/images/public` 目录使用 `bingwall:www-data` 和 `2750` 权限，应用可写入，Nginx 可读取。
- 临时目录、失败目录、数据库目录和配置目录不暴露给 Nginx。

### 2. 安装 Python 依赖并初始化配置

```bash
sudo -u bingwall bash -lc 'cd /opt/bingwall/app && python3.14 -m venv .venv'
sudo -u bingwall bash -lc 'cd /opt/bingwall/app && .venv/bin/pip install --upgrade pip'
sudo -u bingwall bash -lc 'cd /opt/bingwall/app && .venv/bin/pip install -e .'
sudo install -o bingwall -g bingwall -m 0640 /opt/bingwall/app/deploy/systemd/bingwall.env.example /etc/bingwall/bingwall.env
sudoedit /etc/bingwall/bingwall.env
```

修改 `/etc/bingwall/bingwall.env` 时至少需要确认：

- `BINGWALL_APP_BASE_URL` 改成实际访问域名或 IP
- `BINGWALL_SECURITY_SESSION_SECRET` 改成不少于 `32` 字节的随机值
- 如需调整监听端口，必须同步修改 `deploy/systemd/bingwall-api.service`

### 3. 初始化数据库并安装服务配置

```bash
sudo -u bingwall bash -lc 'set -a && source /etc/bingwall/bingwall.env && set +a && cd /opt/bingwall/app && .venv/bin/python -m app.repositories.migrations'
sudo install -o root -g root -m 0644 /opt/bingwall/app/deploy/systemd/bingwall-api.service /etc/systemd/system/bingwall-api.service
sudo install -o root -g root -m 0644 /opt/bingwall/app/deploy/systemd/bingwall.tmpfiles.conf /etc/tmpfiles.d/bingwall.conf
sudo install -o root -g root -m 0644 /opt/bingwall/app/deploy/nginx/bingwall.conf /etc/nginx/sites-available/bingwall.conf
sudo ln -sf /etc/nginx/sites-available/bingwall.conf /etc/nginx/sites-enabled/bingwall.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/bingwall.conf
sudo systemctl daemon-reload
sudo systemctl enable --now bingwall-api.service
sudo nginx -t
sudo systemctl reload nginx
```

### 4. 最小上线检查

```bash
curl http://127.0.0.1/api/health/live
curl http://127.0.0.1/api/health/ready
curl http://127.0.0.1/api/health/deep
curl http://127.0.0.1/api/public/site-info
curl http://127.0.0.1/
journalctl -u bingwall-api.service -n 50 --no-pager
tail -n 50 /var/log/bingwall/nginx.access.log
```

如果前面已经执行过 Bing 采集并生成正式图片资源，还应额外检查：

```bash
curl -I http://127.0.0.1/images/<正式资源相对路径>
```

仓库已提供的生产部署模板文件：

- [deploy/nginx/bingwall.conf](/home/ops/Projects/BingWall/deploy/nginx/bingwall.conf)
- [deploy/systemd/bingwall-api.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-api.service)
- [deploy/systemd/bingwall.tmpfiles.conf](/home/ops/Projects/BingWall/deploy/systemd/bingwall.tmpfiles.conf)
- [deploy/systemd/bingwall.env.example](/home/ops/Projects/BingWall/deploy/systemd/bingwall.env.example)
