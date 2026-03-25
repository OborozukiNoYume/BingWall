# CHANGELOG

## 2026-03-25T12:27:30Z

### 变更内容

- 新增 [scripts/verify_t1_6.py](scripts/verify_t1_6.py)，把阶段一 `T1.6` 剩余的部署验收固化为可重复执行的自动化脚本，统一覆盖 `systemd` 单元离线校验、`tmpfiles` 模板校验、临时 `systemd --user` 服务重启验证、Docker 化 `nginx` 真实代理验证，以及页面/API/图片与日志检查
- 更新 [Makefile](Makefile)，新增 `make verify-deploy` 统一命令入口，避免手工拼接部署验收命令
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [docs/TODO.md](docs/TODO.md)，把 `T1.6` 状态从“待目标机部署验收”同步为“已完成自动化验收”，并补充验收边界、使用方式和后续优先级

### 变更原因

- 完成阶段一 `T1.6`，把原先依赖人工执行的部署验收收敛为仓库内可重复运行的自动化流程
- 在不修改当前机器系统级 Nginx 和 systemd 配置的前提下，补齐公开页面、公开 API、静态资源、图片资源和日志链路的真实访问验证
- 为阶段二开始前的回归验证保留稳定入口，避免后续修改部署模板后无法快速复验

### 依赖变更

- 无新增第三方依赖
- 使用现有系统能力：`docker`、`systemd-analyze`、`systemd-tmpfiles`、`systemd-run`、`systemctl --user`
- 变更时间：`2026-03-25T12:27:30Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖阶段一部署验收脚本、统一命令入口、部署说明文档、项目状态文档和阶段 TODO 状态同步
- 不涉及数据库表结构、采集链路、公开 API 规则、公开前端交互或任何阶段二业务逻辑
- 验收脚本默认使用临时本地端口和临时工作目录，不会改写 `/etc/systemd/system`、`/etc/nginx` 或现有目标机配置

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/unit/test_deploy_templates.py`
- 执行 `./.venv/bin/python scripts/verify_t1_6.py`
- 执行 `make verify`

### 回滚说明

- 如需回滚本次变更，可删除 `scripts/verify_t1_6.py`、恢复 [Makefile](Makefile) 中的 `make verify-deploy` 入口，并回退相关文档更新，或执行 `git revert` 回退本次提交
- 回滚后仓库将恢复到“已具备部署模板和说明，但部署验收仍主要依赖人工执行”的状态
- 回滚不影响现有数据库、采集逻辑、公开 API、公开前端页面和部署模板本身

## 2026-03-24T14:01:12Z

### 变更内容

- 新增 [deploy/nginx/bingwall.conf](deploy/nginx/bingwall.conf)、[deploy/systemd/bingwall-api.service](deploy/systemd/bingwall-api.service)、[deploy/systemd/bingwall.tmpfiles.conf](deploy/systemd/bingwall.tmpfiles.conf) 与 [deploy/systemd/bingwall.env.example](deploy/systemd/bingwall.env.example)，落地阶段一 `T1.6` 所需的 Nginx 路由模板、`systemd` 服务模板、目录权限模板和生产环境变量示例
- 新增 [tests/unit/test_deploy_templates.py](tests/unit/test_deploy_templates.py)，约束部署模板中的关键路由、环境文件和权限配置，避免后续修改破坏一期单机部署假设
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [docs/TODO.md](docs/TODO.md)，补充可复制部署命令、最小上线检查、`T1.6` 状态和当前剩余验证边界

### 变更原因

- 落实阶段一 `T1.6`，把公开链路的单机部署要求从纯文档约束推进为可复用的仓库内模板
- 为后续阶段二健康检查、巡检、备份与后台能力提供稳定的部署底座
- 保持保守范围，不引入容器、反向代理新特性、`gunicorn` 或新的第三方依赖

### 依赖变更

- 无新增第三方依赖
- 新增部署模板：`deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf`、`deploy/systemd/bingwall.env.example`
- 变更时间：`2026-03-24T14:01:12Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖单机部署配置模板、目录权限约定、生产环境变量示例和部署说明文档
- Nginx 将区分公开页面、公开 API、页面静态资源和正式图片资源访问路径
- FastAPI 进程将以 `systemd` 受管服务方式启动，并通过受控环境文件读取配置
- 不涉及数据库表结构、采集逻辑、公开 API 业务规则或前端页面交互变更

### 验证步骤

- 执行 `make format`
- 执行 `make lint`
- 执行 `make typecheck`
- 执行 `make test`
- 执行 `systemd-analyze security --offline=yes deploy/systemd/bingwall-api.service`
- 执行 `systemd-tmpfiles --create --graceful --root="<临时目录>" /home/ops/Projects/BingWall/deploy/systemd/bingwall.tmpfiles.conf`
- 在安装了 Nginx 的目标机执行 `nginx -t`

### 回滚说明

- 如需回滚本次变更，可恢复部署模板、模板测试与文档更新，或执行 `git revert` 回退本次提交
- 如目标环境已经安装了新的 `systemd`、`tmpfiles.d` 和 Nginx 配置，应同时删除 `/etc/systemd/system/bingwall-api.service`、`/etc/tmpfiles.d/bingwall.conf`、`/etc/nginx/sites-available/bingwall.conf` 及对应启用链接
- 回滚后仓库将退回到已具备公开页面和公开 API，但尚未提供单机部署模板与最小部署检查说明的状态

## 2026-03-24T13:51:37Z

### 变更内容

- 新增 [app/web/routes.py](app/web/routes.py)、[app/web/__init__.py](app/web/__init__.py)、[web/public/assets/site.css](web/public/assets/site.css) 与 [web/public/assets/site.js](web/public/assets/site.js)，落地首页 `/`、列表页 `/wallpapers`、详情页 `/wallpapers/{wallpaper_id}` 以及公开前端所需的样式和前端脚本
- 更新 [app/main.py](app/main.py)，挂载公开页面路由、`/assets/*` 页面静态资源和 `/images/*` 本地开发图片访问目录
- 新增 [tests/integration/test_public_frontend.py](tests/integration/test_public_frontend.py)，覆盖公开页面外壳、静态资源引用和图片目录访问
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md) 与 [docs/TODO.md](docs/TODO.md)，同步 `T1.5` 已完成状态、公开页面验证方式和下一阶段优先级

### 变更原因

- 落实阶段一 `T1.5`，把首页、列表页、详情页和错误提示从设计文档推进为可访问页面
- 在不引入新前端框架或构建链的前提下，为一期公开链路提供最保守可运行的页面实现
- 为后续 `T1.6` 单机部署闭环提供公开页面入口和静态资源结构

### 依赖变更

- 无新增第三方依赖
- 变更时间：`2026-03-24T13:51:37Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖公开页面路由、静态资源、浏览器端公开 API 调用和本地开发图片访问挂载
- 首页、列表页和详情页仅通过 `/api/public/*` 读取业务数据，不直接访问数据库
- 不涉及后台页面、后台 API、Nginx 配置、systemd 配置或数据库迁移结构变更

### 验证步骤

- 执行 `make format`
- 执行 `make lint`
- 执行 `make typecheck`
- 执行 `make test`
- 执行 `cp .env.example .env`
- 执行 `make db-migrate`
- 执行 `curl http://127.0.0.1:8000/`
- 执行 `curl "http://127.0.0.1:8000/wallpapers?page=1&market_code=en-US"`
- 执行 `curl http://127.0.0.1:8000/wallpapers/1`

### 回滚说明

- 如需回滚本次变更，可恢复公开页面路由、静态资源、前端测试与文档更新，或执行 `git revert` 回退本次提交
- 如本地运行依赖 `/images/*` 开发挂载，可一并回退 [app/main.py](app/main.py) 中的图片目录挂载
- 回滚后仓库将退回到具备公开 API 最小集但尚未提供基础公开前端的状态

## 2026-03-24T13:40:19Z

### 变更内容

- 新增 [app/repositories/public_repository.py](app/repositories/public_repository.py)、[app/services/public_catalog.py](app/services/public_catalog.py)、[app/schemas/public.py](app/schemas/public.py) 与 [app/schemas/common.py](app/schemas/common.py)，落地公开列表、详情、筛选项和站点信息的查询结构、响应结构与分页结构
- 新增 [app/api/public/routes.py](app/api/public/routes.py)、更新 [app/api/router.py](app/api/router.py)、[app/api/public/__init__.py](app/api/public/__init__.py) 与 [app/main.py](app/main.py)，接入 `/api/public/wallpapers`、`/api/public/wallpapers/{wallpaper_id}`、`/api/public/wallpaper-filters`、`/api/public/site-info` 四个接口，并补齐统一错误响应、`trace_id` 回传和访问日志
- 更新 [app/core/config.py](app/core/config.py)、[.env.example](.env.example) 与 [tests/conftest.py](tests/conftest.py)，补充 `BINGWALL_SITE_NAME`、`BINGWALL_SITE_DESCRIPTION` 最小站点配置
- 新增 [tests/integration/test_public_api.py](tests/integration/test_public_api.py)，覆盖公开可见性过滤、分页、筛选项、站点信息、不可下载详情和统一错误响应
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md) 与 [docs/TODO.md](docs/TODO.md)，同步 `T1.4` 已完成状态、公开接口验证方式和下一阶段优先级

### 变更原因

- 落实阶段一 `T1.4`，把公开 API 最小集从设计文档推进为可调用代码
- 为后续 `T1.5` 公开前端提供稳定的数据接口、统一响应格式和错误处理口径
- 保持保守范围，不引入 ORM、分页库、鉴权框架或额外第三方依赖

### 依赖变更

- 无新增第三方依赖
- 新增配置项：`BINGWALL_SITE_NAME`、`BINGWALL_SITE_DESCRIPTION`
- 变更时间：`2026-03-24T13:40:19Z`
- 依赖类型：配置项变更，不涉及直接或间接第三方包升级

### 影响范围

- 影响范围覆盖公开 API 路由、公开查询服务、统一成功响应、统一错误响应和访问日志
- 公开接口只返回已启用、允许公开、资源已就绪且处于发布时间窗口内的内容
- 不涉及前端页面、后台鉴权、后台管理、部署脚本或数据库迁移结构变更

### 验证步骤

- 执行 `make format`
- 执行 `make lint`
- 执行 `make typecheck`
- 执行 `make test`
- 执行 `cp .env.example .env`
- 执行 `make db-migrate`
- 执行 `curl http://127.0.0.1:8000/api/public/site-info`
- 执行 `curl "http://127.0.0.1:8000/api/public/wallpapers?page=1&page_size=20&sort=date_desc"`

### 回滚说明

- 如需回滚本次变更，可恢复公开 API 路由、查询服务、响应 schema、测试与文档更新，或执行 `git revert` 回退本次提交
- 如环境中已经依赖 `BINGWALL_SITE_NAME`、`BINGWALL_SITE_DESCRIPTION` 配置，可同时回退对应环境变量设置
- 回滚后仓库将退回到已具备 Bing 采集主链路但尚未提供公开 API 最小集的状态

## 2026-03-24T13:14:16Z

### 变更内容

- 新增 [app/collectors/bing.py](app/collectors/bing.py)、[app/services/bing_collection.py](app/services/bing_collection.py)、[app/domain/collection.py](app/domain/collection.py)，落地 Bing 元数据拉取、字段映射、下载与采集主链路
- 新增 [app/repositories/collection_repository.py](app/repositories/collection_repository.py) 与 [app/repositories/file_storage.py](app/repositories/file_storage.py)，封装采集任务、壁纸、资源、任务明细写入，以及临时目录、正式目录、失败隔离目录的文件操作
- 更新 [app/core/config.py](app/core/config.py)、[.env.example](.env.example) 与 [Makefile](Makefile)，补充 Bing 采集开关、默认地区、超时、重试次数配置，以及 `make collect-bing MARKET=en-US COUNT=1` 手动采集命令
- 新增 [tests/integration/test_bing_collection_service.py](tests/integration/test_bing_collection_service.py)，覆盖首次采集、业务主键重复、`source_url_hash` 重复、下载失败与重试耗尽四类集成测试
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [docs/TODO.md](docs/TODO.md)，同步 `T1.3` 已完成状态、运行命令、验证方式与下一阶段优先级

### 变更原因

- 落实阶段一 `T1.3`，把 Bing 采集、去重、任务记录、下载入库和资源状态联动从设计文档推进为可运行代码
- 为后续 `T1.4` 公开 API 提供真实内容数据、资源文件和任务观测基础
- 继续保持保守实现，不引入 ORM、任务队列或额外第三方 HTTP 依赖

### 依赖变更

- 无新增第三方依赖
- Bing 元数据请求与图片下载基于 Python 标准库 `urllib.request`
- 新增配置项：`BINGWALL_COLLECT_BING_ENABLED`、`BINGWALL_COLLECT_BING_DEFAULT_MARKET`、`BINGWALL_COLLECT_BING_TIMEOUT_SECONDS`、`BINGWALL_COLLECT_BING_MAX_DOWNLOAD_RETRIES`
- 变更时间：`2026-03-24T13:14:16Z`

### 影响范围

- 影响范围覆盖 Bing 采集主链路、任务记录、资源下载与本地文件落盘
- 采集成功后会向数据库写入 `wallpapers`、`image_resources`、`collection_tasks`、`collection_task_items`
- 采集成功后会向正式资源目录写入图片文件；校验失败时会写入失败隔离目录
- 不涉及公开 API、后台 API、前端页面或生产环境部署配置

### 验证步骤

- 执行 `make format`
- 执行 `make verify`
- 执行 `cp .env.example .env`
- 执行 `make db-migrate`
- 执行 `make collect-bing MARKET=en-US COUNT=1`
- 重复执行一次 `make collect-bing MARKET=en-US COUNT=1`，确认命中重复而不重复建内容

### 回滚说明

- 如需回滚本次变更，可恢复采集模块、仓储模块、测试与文档更新，或执行 `git revert` 回退本次提交
- 如数据库和图片目录已经执行过真实采集，回滚前应先备份 SQLite 文件与正式资源目录、失败隔离目录
- 回滚后仓库将退回到具备数据库迁移基线但尚无 Bing 采集与资源入库主链路的状态

## 2026-03-24T12:54:37Z

### 变更内容

- 新增 [app/repositories/migrations/runner.py](app/repositories/migrations/runner.py)、[app/repositories/migrations/__main__.py](app/repositories/migrations/__main__.py) 与 [app/repositories/migrations/versions/V0001__baseline.sql](app/repositories/migrations/versions/V0001__baseline.sql)，落地 SQLite 版本化迁移基线、`schema_migrations` 管理表和 `T1.2` 的首个基线迁移脚本
- 新增 [app/repositories/sqlite.py](app/repositories/sqlite.py)，统一 SQLite 连接和外键约束启用方式
- 更新 [Makefile](Makefile) 与 [pyproject.toml](pyproject.toml)，补充 `make db-migrate` 数据库初始化命令，并将迁移 SQL 文件纳入包数据
- 新增 [tests/integration/test_sqlite_migrations.py](tests/integration/test_sqlite_migrations.py)，覆盖空库迁移、重复执行迁移、表结构、索引和审计外键校验
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [docs/TODO.md](docs/TODO.md)，同步 `T1.2` 已完成状态、数据库初始化命令、验证方式与下一阶段优先级

### 变更原因

- 落实阶段一 `T1.2`，把数据模型说明中的核心实体、唯一约束和关键索引落成真实 SQLite 表结构
- 为后续 `T1.3` 采集链路提供可重复执行、可审计、无需手工改库的数据库基线
- 在不引入 ORM 或外部迁移框架的前提下，采用更保守的标准库方案控制范围和依赖

### 依赖变更

- 无新增第三方依赖
- 迁移执行基于 Python 标准库 `sqlite3`
- 包数据变更：通过 [pyproject.toml](pyproject.toml) 纳入 `app.repositories.migrations` 下的 `versions/*.sql`
- 变更时间：`2026-03-24T12:54:37Z`

### 影响范围

- 影响范围覆盖 SQLite 数据库初始化、迁移执行和核心表结构落地
- 已落地 `wallpapers`、`image_resources`、`collection_tasks`、`collection_task_items`、`admin_users`、`audit_logs` 六张核心表
- 已落地 `source_type + wallpaper_date + market_code` 唯一约束，以及公开查询、任务查询和状态筛选所需关键索引
- 不涉及 Bing 采集逻辑、公开 API、后台 API、前端页面或生产部署配置

### 验证步骤

- 执行 `make format`
- 执行 `make verify`
- 执行 `cp .env.example .env`
- 执行 `make db-migrate`
- 检查数据库中是否存在六张核心表、`schema_migrations` 管理表和关键索引
- 重复执行一次 `make db-migrate`，确认不会重复落库或要求手工改库

### 回滚说明

- 如需回滚本次变更，可恢复迁移模块、迁移脚本、测试与文档更新，或执行 `git revert` 回退本次提交
- 如数据库已经执行过本次基线迁移，回滚代码前应先备份当前 SQLite 文件，再按环境策略决定是否回退数据库文件
- 回滚后仓库将退回到仅具备最小应用骨架、尚无数据库迁移与真实表结构的状态

## 2026-03-23T13:59:42Z

### 变更内容

- 新增 `.python-version`、`.nvmrc`、`.env.example`、`pyproject.toml`、`requirements.lock.txt`、`.gitignore` 与 `Makefile`，固定 `Python 3.14.2`、`Node.js 24.13.0` 运行时基线，并提供 `make setup`、`make verify`、`make run` 统一命令入口
- 新增 `app/` 最小后端工程骨架，包含统一配置加载入口、日志基础设施、根路由和 `GET /api/health/live` 最小健康检查
- 新增 `tests/unit/test_config.py` 与 `tests/smoke/test_health_live.py`，覆盖关键配置缺失、会话密钥校验和最小 HTTP 响应
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [docs/TODO.md](docs/TODO.md)，同步 `T1.1` 已实现状态、运行命令、验证方式与后续缺口

### 变更原因

- 落实阶段一 `T1.1`，把仓库从纯文档状态推进到可启动、可验证、可继续承载后续模块的最小后端工程状态
- 先完成最小 FastAPI 服务、统一配置入口和基础验证命令，为后续数据库、采集和 API 实现提供稳定底座

### 依赖变更

- 直接依赖：`fastapi==0.116.1`，用途是提供最小 API 服务与健康检查接口
- 直接依赖：`pydantic-settings==2.11.0`，用途是提供统一配置加载与启动期校验
- 直接依赖：`uvicorn==0.35.0`，用途是提供本地开发启动与 HTTP 服务承载
- 直接开发依赖：`pytest==8.4.2`，用途是执行单元测试与冒烟测试
- 直接开发依赖：`ruff==0.13.3`，用途是执行格式化与静态检查
- 直接开发依赖：`mypy==1.18.2`，用途是执行类型检查
- 直接开发依赖：`httpx==0.28.1`，用途是支撑 FastAPI 测试客户端
- 间接依赖：已通过 `pip freeze --all` 生成 [requirements.lock.txt](requirements.lock.txt)，记录本次安装时解析出的精确版本集合
- 变更时间：`2026-03-23T13:59:42Z`

### 影响范围

- 影响范围覆盖后端工程初始化与文档同步
- 不涉及数据库表结构和迁移
- 不涉及采集逻辑、公开 API 业务接口、后台 API 或前端页面
- 新增最小健康检查与开发命令后，仓库从不可运行转为可在本地最小启动

### 验证步骤

- 执行 `make setup`
- 执行 `make verify`
- 以 `.env.example` 的配置值启动 `make run`
- 请求 `GET /api/health/live`，确认返回 `200` 和最小 JSON 响应
- 确认缺失关键配置时，`tests/unit/test_config.py` 会触发启动期校验失败

### 回滚说明

- 如需回滚本次变更，可恢复新增的工程初始化文件与文档更新，或执行 `git revert` 回退本次提交
- 回滚后仓库将退回到仅包含文档、尚无最小可执行后端实现的状态

## 2026-03-23T13:33:04Z

### 变更内容

- 更新 [README.md](README.md)，同步当前阶段状态，并补充已确认的一期开发运行时基线 `Python 3.14.2`、`Node.js 24.13.0`
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md)，将项目状态调整为阶段一 `T1.1` 前置准备阶段，并记录已确认的开发运行时基线
- 更新 [docs/deployment-runbook.md](docs/deployment-runbook.md)，将目标环境中的 `Python` 与 `Node.js` 运行时版本改为明确记录，补充“已确认基线但尚未生成锁定文件”的说明

### 变更原因

- 根据当前机器已确认可用的开发环境，先固定一期实现所使用的运行时基线
- 关闭“运行时版本尚未确定”的文档缺口，为后续阶段一代码初始化提供统一依据

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖安装
- 不涉及运行时行为变更

### 验证步骤

- 确认 [README.md](README.md) 已记录 `Python 3.14.2` 和 `Node.js 24.13.0`
- 确认 [PROJECT_STATE.md](PROJECT_STATE.md) 中“当前阶段”“当前技术路线”“未完成内容”与运行时基线表述一致
- 确认 [docs/deployment-runbook.md](docs/deployment-runbook.md) 的目标环境表已记录精确运行时版本，且未误写为“已存在锁定文件”

### 回滚说明

- 如需回滚本次变更，可恢复 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [CHANGELOG.md](CHANGELOG.md) 的上一版本
- 本次变更仅影响文档说明，不影响现有代码、依赖或数据

## 2026-03-23T13:18:49Z

### 变更内容

- 更新 [docs/TODO.md](docs/TODO.md)，为 `T1.1` 到 `T3.6` 的既有 TODO 补充可勾选子任务 Checklist

### 变更原因

- 将已有阶段路线图细化为可直接执行和勾选的开发子任务
- 让每条 TODO 与现有模块说明、数据模型、API 约定和部署约束形成更明确的落地路径

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认 `docs/TODO.md` 中每个现有 TODO 均新增且仅新增一个“子任务”段落
- 确认未修改 TODO 编号、阶段归属、`depends_on`、验收标准、`source_design` 和 `source_spec`
- 确认每条子任务均使用动词开头，且包含核心业务实现与测试或验证动作

### 回滚说明

- 如需回滚本次变更，可恢复本次修改前的 `docs/TODO.md` 与 `CHANGELOG.md`
- 本次变更仅影响文档说明，不影响现有代码或数据

## 2026-03-23T12:57:44Z

### 变更内容

- 更新 [docs/TODO.md](docs/TODO.md)，修正 `T2.4`、`T3.4` 依赖与验收口径，并补充采集重试、恢复验证、搜索响应时间要求
- 更新 [docs/data-model.md](docs/data-model.md)，补齐 `admin_sessions`、`tags`、`wallpaper_tags`、`download_events` 数据结构，并明确 `resource_status` 与 `image_status` 的同步责任
- 更新 [docs/api-conventions.md](docs/api-conventions.md)，补充后台登出接口、标签与下载登记扩展接口，并澄清后台日志查询与结构化任务日志的关系
- 更新 [docs/module-overview.md](docs/module-overview.md) 与 [docs/system-design.md](docs/system-design.md)，明确调度模块只负责触发，补充 API 路由前缀和运维告警基线
- 更新 [docs/deployment-runbook.md](docs/deployment-runbook.md)，补齐会话密钥、密码策略和默认告警阈值要求
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md)，同步最新文档决策与开放问题

### 变更原因

- 修正文档中已确认的依赖链和职责边界不一致
- 补齐阶段二和阶段三路线图已承诺但尚未落到数据模型或 API 契约的内容
- 让状态联动、会话管理和运维配置要求具备更明确的执行口径

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认 `docs/TODO.md` 的依赖拓扑与 `depends_on` 字段不再互相冲突
- 确认标签、会话和下载登记在 TODO、数据模型、API 约定之间均有对应落点
- 确认公开可见规则统一为 `content_status`、`is_public`、`image_status` 与 `resource_status` 联合约束
- 确认调度模块与采集模块的职责边界在模块说明和系统设计中一致
- 确认部署文档中的安全与告警基线已给出可执行的默认值

### 回滚说明

- 如需回滚本次变更，可恢复本次修改前的相关文档版本
- 本次变更仅影响文档说明，不影响现有代码或数据

## 2026-03-23T12:30:47Z

### 变更内容

- 更新 [docs/system-design.md](docs/system-design.md)，统一公开筛选与公开可见规则
- 更新 [docs/data-model.md](docs/data-model.md)，明确 `image_status` 与 `resource_status` 的关系，并补充下载可见性规则
- 更新 [docs/api-conventions.md](docs/api-conventions.md)，澄清统一响应结构示例语义，并补齐站点信息、后台详情、日志和审计接口契约
- 更新 [docs/deployment-runbook.md](docs/deployment-runbook.md)，区分阶段一公开链路最小检查与阶段二完整上线检查
- 更新 [docs/TODO.md](docs/TODO.md)，同步调整 API、部署和验收口径
- 更新 [docs/README.md](docs/README.md)，同步 TODO 文档定位

### 变更原因

- 修正文档间公开筛选规则冲突
- 补齐设计总纲已要求但 API 契约缺失的接口
- 让部署检查与阶段路线图保持一致
- 让 TODO 的验收标准与最新文档口径一致

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认公开可见规则在系统设计、数据模型、API 契约和 TODO 中一致
- 确认 API 文档中的示例已明确为 `data` 字段结构
- 确认后台详情、任务详情、日志和审计接口在 API 文档中已有定义
- 确认部署文档的阶段一和阶段二检查项与 TODO 阶段边界一致

### 回滚说明

- 如需回滚本次变更，可恢复本次修改前的相关文档版本
- 本次变更仅影响文档说明，不影响现有代码或数据

## 2026-03-23T12:11:15Z

### 变更内容

- 更新 [docs/TODO.md](docs/TODO.md)
- 对阶段 TODO 做系统级校准，补充依赖拓扑、来源标注、输入输出和状态字段
- 合并重复或过细任务：`TODO-3 + TODO-4`、`TODO-10 + TODO-11`
- 强化每条 TODO 的验收标准和可观测性要求

### 变更原因

- 让路线图与系统设计总纲及专项文档保持一致
- 修正任务依赖，避免后台绕过 API、部署顺序失真和任务粒度不一致
- 让后续实施时可以直接按任务来源、输入输出和验收条件执行

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认每条 TODO 都标注了 `source_design` 和 `source_spec`
- 确认所有任务均带有 `depends_on`、`输入`、`输出`、`验收标准` 和 `status`
- 确认不存在循环依赖和跨阶段反向依赖
- 确认每阶段任务数均不超过 8

### 回滚说明

- 如需回滚本次变更，可恢复上一版 `docs/TODO.md`
- 本次变更仅影响路线图结构，不影响已有设计总纲和其他文档边界

## 2026-03-23T00:00:00Z

### 变更内容

- 新增文档总览：[docs/README.md](docs/README.md)
- 新增模块说明：[docs/module-overview.md](docs/module-overview.md)
- 新增数据模型说明：[docs/data-model.md](docs/data-model.md)
- 新增 API 约定：[docs/api-conventions.md](docs/api-conventions.md)
- 新增部署与运行说明：[docs/deployment-runbook.md](docs/deployment-runbook.md)
- 新增阶段 TODO 路线图：[docs/TODO.md](docs/TODO.md)
- 新增项目状态文件：`PROJECT_STATE.md`
- 更新 `README.md`，补充项目说明和文档入口

### 变更原因

- 以 `docs/system-design.md` 为总纲，补齐实施前缺失的配套文档
- 让后续开发、验收、部署和协作有统一依据
- 将阶段目标拆成可执行 TODO，降低后续实施歧义

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认 `README.md` 已能作为项目入口定位所有核心文档
- 确认 `docs/` 下已有模块说明、数据模型、API 约定、部署说明和路线图
- 确认路线图中的每条 TODO 都包含依赖关系和验收标准
- 确认文档之间技术路线保持一致，均以单机一期方案为前提

### 回滚说明

- 如需回滚本次变更，可删除新增文档并恢复 `README.md`
- 本次变更仅涉及文档，不影响运行环境和数据文件
