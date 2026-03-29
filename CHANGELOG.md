# CHANGELOG

## 2026-03-29T00:40:29Z

### 变更内容

- 更新 [app/services/source_collection.py](app/services/source_collection.py) 与 [app/repositories/collection_repository.py](app/repositories/collection_repository.py)，把同业务键去重逻辑收紧为“仅对已存在资源记录的壁纸直接判定为重复”；若历史异常中断后只留下壁纸主体、尚未写入任何 `image_resources`，则后续采集会继续补齐资源而不是直接跳过
- 更新 [tests/integration/test_bing_collection_service.py](tests/integration/test_bing_collection_service.py)，新增“已有零资源半成品记录时可修复式重试”的集成测试，确保修复不会破坏既有重复跳过行为
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md) 与 [CHANGELOG.md](CHANGELOG.md)，同步记录本次修复的原因、影响范围、验证方式和回滚说明

### 变更原因

- 本地数据库在缺少 `V0007` 迁移时执行过一次 Bing 采集，导致壁纸主体已写入，但 `image_resources` 因表结构旧版本报错而未能创建
- 现有去重逻辑只要命中同业务键就直接跳过，没有区分“完整已采集数据”和“只有主体、没有资源的半成品记录”
- 因此本次采用最保守修复：不改变既有完整重复数据的跳过规则，只为“零资源半成品”补一个可恢复的重试入口

### 依赖变更

- 无新增第三方依赖
- 无新增数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-29T00:40:29Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖采集服务的业务键去重判定、采集仓储的资源存在性判断，以及对应的 Bing 采集集成测试和项目文档
- 现在当历史异常中断留下零资源半成品时，再次执行同业务键采集会继续生成原图、缩略图、预览图和下载图，而不是直接记为重复
- 本次不包含数据库结构变更、公开 API 字段调整、后台页面改版或更广义的失败重试策略重写

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_bing_collection_service.py`
- 执行 `./.venv/bin/python -m ruff check app/services/source_collection.py app/repositories/collection_repository.py tests/integration/test_bing_collection_service.py`
- 执行 `./.venv/bin/python -m mypy app/services/source_collection.py app/repositories/collection_repository.py tests/integration/test_bing_collection_service.py`

### 回滚说明

- 如需回滚本次变更，可恢复 [app/services/source_collection.py](app/services/source_collection.py) 中“命中同业务键即直接跳过”的旧逻辑，并回退新增测试和文档记录，或执行 `git revert` 回退本次提交
- 回滚后，历史异常留下的零资源半成品记录会再次被当成重复数据直接跳过，仍需人工清理或手动修库后再采集

## 2026-03-28T15:43:24Z

### 变更内容

- 更新 [app/collectors/bing.py](app/collectors/bing.py)，把 Bing 下载分辨率候选列表进一步收敛为 5 种：`UHD`、`1920x1200`、`1920x1080`、`1366x768`、`720x1280`
- 更新 [tests/unit/test_bing_collector.py](tests/unit/test_bing_collector.py)，把断言从“15 种官方分辨率”调整为“当前允许的 5 种分辨率”，避免未来误把其他尺寸重新加回
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/api-conventions.md](docs/api-conventions.md)、[docs/data-model.md](docs/data-model.md) 与 [CHANGELOG.md](CHANGELOG.md)，把上一版“15 种”说明统一改为当前 5 种口径

### 变更原因

- 你进一步收敛了业务要求：当前只保留 `3840x2160`、`1920x1200`、`1920x1080`、`1366x768`、`720x1280` 这 5 种分辨率
- 因此上一版“15 种官方分辨率”的实现和文档已经不再符合当前需求，需要立即缩小候选表和测试断言，避免继续抓取不需要的尺寸

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-28T15:43:24Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖 Bing 下载候选地址生成、对应单元测试和项目文档
- 现在 Bing 只会尝试 5 种分辨率，不再抓取 `1280x768`、`1280x720`、`1024x768`、`800x600`、`800x480`、`480x800` 等其他尺寸
- 本次不包含数据库结构调整、公开 API 字段变化或前端页面改版

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/unit/test_bing_collector.py tests/integration/test_bing_collection_service.py tests/integration/test_public_api.py`
- 执行 `./.venv/bin/python -m ruff check app tests scripts`
- 执行 `./.venv/bin/python -m mypy app tests scripts/create_scheduled_collection_tasks.py scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可恢复 [app/collectors/bing.py](app/collectors/bing.py) 中更宽的候选分辨率列表，并回退测试与文档同步内容，或执行 `git revert` 回退本次提交
- 回滚后系统会重新抓取当前已移除的其他尺寸

## 2026-03-28T15:30:09Z

### 变更内容

- 更新 [app/domain/collection.py](app/domain/collection.py)、[app/collectors/bing.py](app/collectors/bing.py)、[app/services/source_collection.py](app/services/source_collection.py) 与 [app/services/bing_collection.py](app/services/bing_collection.py)，为采集元数据新增多分辨率下载变体描述，并把 Bing 抓取链路从“只抓一张下载图”扩展为“按已知官方分辨率逐个尝试、成功的全部落盘落库”；同一张 Bing 壁纸现在会保留多条 `download` 资源，默认原图优先使用最高可用分辨率
- 新增迁移 [app/repositories/migrations/versions/V0007__image_resource_download_resolution_variants.sql](app/repositories/migrations/versions/V0007__image_resource_download_resolution_variants.sql)，为 `image_resources` 增加 `variant_key` 字段，并把唯一约束从 `(wallpaper_id, resource_type)` 调整为 `(wallpaper_id, resource_type, variant_key)`，允许同一壁纸存在多条不同分辨率的下载资源
- 更新 [app/repositories/download_repository.py](app/repositories/download_repository.py)、[app/repositories/public_repository.py](app/repositories/public_repository.py)、[app/services/downloads.py](app/services/downloads.py)、[app/services/public_catalog.py](app/services/public_catalog.py) 与 [app/schemas/public.py](app/schemas/public.py)，公开详情现在会返回 `download_variants` 多分辨率列表，`download_url` 保留为默认下载地址，`POST /api/public/download-events` 则支持按指定 `resource_id` 跳转对应分辨率
- 更新 [tests/integration/test_bing_collection_service.py](tests/integration/test_bing_collection_service.py)、[tests/integration/test_public_api.py](tests/integration/test_public_api.py)、[tests/integration/test_sqlite_migrations.py](tests/integration/test_sqlite_migrations.py) 等测试，补齐 Bing 多分辨率入库、公开详情返回全部分辨率、指定资源下载登记、迁移结构和资源状态兼容回归
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/api-conventions.md](docs/api-conventions.md)、[docs/data-model.md](docs/data-model.md) 与 [CHANGELOG.md](CHANGELOG.md)，同步记录本次多分辨率抓取、接口返回、数据结构、验证方式和回滚说明

### 变更原因

- 现有 Bing 抓取链路只保存单一下载尺寸，无法满足“同一张图抓取 Bing 所有分辨率”的需求
- 在现有设计里，`image_resources` 对同一 `resource_type` 只允许一条记录，这会直接阻止多分辨率下载资源入库
- 因此本次采用最保守且可交付的方案：保留现有 `original / thumbnail / preview` 语义不变，只把多分辨率能力扩展到 `download` 资源，并复用既有公开详情和下载登记链路

### 依赖变更

- 无新增第三方依赖
- 新增数据库迁移：`V0007__image_resource_download_resolution_variants.sql`
- 变更时间：`2026-03-28T15:30:09Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖 Bing 采集、图片资源唯一约束、公开详情返回结构、下载登记目标解析、资源状态汇总逻辑，以及相关集成测试和文档
- 公开详情接口现在会同时返回默认 `download_url` 与 `download_variants`；旧客户端继续使用默认下载地址不会中断，新客户端可以按 `resource_id` 选择具体分辨率
- 本次不包含公开页面多分辨率选择器改版、后台详情页分辨率列表展示、对象存储写入链路替换或其他来源的多分辨率适配

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_bing_collection_service.py tests/integration/test_public_api.py tests/integration/test_sqlite_migrations.py tests/integration/test_download_statistics.py tests/integration/test_health_checks.py`
- 执行 `./.venv/bin/python -m pytest tests/integration/test_admin_collection.py tests/integration/test_multi_source_collection.py`
- 执行 `./.venv/bin/python -m ruff check app tests scripts`
- 执行 `./.venv/bin/python -m mypy app tests scripts/create_scheduled_collection_tasks.py scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可回退 `V0007` 迁移、删除 `variant_key` 相关仓储与公开接口扩展、恢复 Bing 单一下载图逻辑，并回退对应测试与文档更新，或执行 `git revert` 回退本次提交
- 回滚后系统会恢复为“每张壁纸只保留一条下载资源记录、公开详情只返回单个 `download_url`、不支持按指定分辨率资源下载”的状态

## 2026-03-28T14:34:00Z

### 变更内容

- 新增 [app/services/scheduled_collection.py](app/services/scheduled_collection.py)、[scripts/create_scheduled_collection_tasks.py](scripts/create_scheduled_collection_tasks.py) 与 [deploy/cron/bingwall-cron](deploy/cron/bingwall-cron)，补齐“按当天 UTC 日期创建固定日期采集任务”的定时入口；脚本会为已启用来源写入 `trigger_type = cron`、`task_type = scheduled_collect`、`date_from = date_to = 当天` 的 `queued` 任务，并在同来源同日期已有非失败 cron 任务时保守跳过
- 更新 [app/repositories/admin_collection_repository.py](app/repositories/admin_collection_repository.py) 与 [Makefile](Makefile)，补充定时建任务所需的近期任务查询方法、`make create-scheduled-collection-tasks` 命令，以及本地联调便捷入口 `make scheduled-collect`
- 新增 [tests/integration/test_scheduled_collection.py](tests/integration/test_scheduled_collection.py)，覆盖定时任务创建、同日非失败任务跳过、失败任务允许重建三个关键场景
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [CHANGELOG.md](CHANGELOG.md)，同步本次定时采集落地方式、影响范围、验证步骤、部署示例与回滚说明

### 变更原因

- 当前后台手动采集已经支持固定日期范围，但仓库里缺少“每天自动按当天日期建任务”的脚本和 `cron` 模板，导致自动采集仍停留在设计层，没有形成可直接部署的闭环
- 直接新起一套独立下载逻辑风险较高，会绕开现有任务状态、日志、重试与后台观测链路
- 因此本次采用更保守的方案：只新增“定时建任务”这一层薄封装，继续复用现有任务消费器执行实际下载

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-28T14:34:00Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖定时采集任务创建脚本、目标机 `cron` 示例模板、命令入口、后台任务记录与对应的集成测试
- 管理后台现在可以看到由 `cron` 自动创建的固定日期采集任务，任务详情中的 `date_from` / `date_to` 会明确显示具体日期，而不是只表现为“最近 N 张”
- 本次不包含后台页面改版、数据库结构调整、调度系统替换、消息队列引入或现有采集下载主链路重写

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_scheduled_collection.py tests/integration/test_admin_collection.py`
- 执行 `./.venv/bin/python -m ruff check app tests scripts`
- 执行 `./.venv/bin/python -m mypy app tests scripts/create_scheduled_collection_tasks.py scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除 `scripts/create_scheduled_collection_tasks.py`、`deploy/cron/bingwall-cron`、`make create-scheduled-collection-tasks` / `make scheduled-collect` 入口，以及对应测试和文档更新，或执行 `git revert` 回退本次提交
- 回滚后仓库将恢复为“只能后台手动创建固定日期任务，或由现有消费器执行 queued 任务，但不提供每日自动创建当天任务脚本”的状态

## 2026-03-27T16:46:29Z

### 变更内容

- 更新 [app/web/routes.py](app/web/routes.py)、[web/public/assets/site.css](web/public/assets/site.css) 与 [tests/integration/test_public_frontend.py](tests/integration/test_public_frontend.py)，在公开首页英雄区新增“今日壁纸 API”和“随机壁纸 API”两个快捷入口，直接展示接口路径并提供跳转链接，同时补齐首页壳与样式断言
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md) 与 [CHANGELOG.md](CHANGELOG.md)，同步记录本次首页入口补充、影响范围、验证方式和回滚说明

### 变更原因

- 当前公开接口已经提供 `/api/public/wallpapers/today` 和 `/api/public/wallpapers/random`，但公开首页只展示最新壁纸列表，没有把这两个单条读取入口明确暴露出来
- 这会让访客即使知道系统有“今日壁纸”和“随机壁纸”能力，也需要自己记接口地址或翻文档，首页引导不完整
- 因此本次采用最保守方式，只补首页入口展示，不改接口字段、不改接口行为，也不扩展到其他页面

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T16:46:29Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖公开首页 HTML 结构、公开首页样式和对应的前端集成测试
- 访客现在访问 `/` 时，可以直接看到“今日壁纸 API”和“随机壁纸 API”两个入口，并打开对应 JSON 返回
- 本次不包含公开 API 逻辑修改、列表页改版、详情页改版、数据库结构调整或后台功能变更

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_public_frontend.py`
- 执行 `./.venv/bin/python -m ruff check app tests`

### 回滚说明

- 如需回滚本次变更，可删除首页新增的两个 API 快捷入口、回退对应样式与测试断言，或执行 `git revert` 回退本次提交
- 回滚后公开首页将恢复为“只展示站点说明和最新壁纸列表，不直接展示 today/random 接口入口”的状态

## 2026-03-27T16:33:08Z

### 变更内容

- 更新 [app/schemas/admin_auth.py](app/schemas/admin_auth.py)、[app/repositories/admin_auth_repository.py](app/repositories/admin_auth_repository.py)、[app/services/admin_auth.py](app/services/admin_auth.py) 与 [app/api/admin/routes.py](app/api/admin/routes.py)，新增 `POST /api/admin/auth/change-password` 后台接口，支持已登录管理员校验当前密码后修改自己的密码，并在成功后使该账号当前后台会话全部失效
- 更新 [app/web/routes.py](app/web/routes.py) 与 [web/admin/assets/admin.js](web/admin/assets/admin.js)，新增 `/admin/change-password` 页面、后台导航入口和修改密码表单交互；提交成功后会清空浏览器中的后台会话并跳回登录页
- 更新 [tests/integration/test_admin_auth.py](tests/integration/test_admin_auth.py) 与 [tests/integration/test_admin_frontend.py](tests/integration/test_admin_frontend.py)，补齐修改密码成功、当前密码错误、确认密码不一致，以及后台页面壳与静态资源接线断言
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/api-conventions.md](docs/api-conventions.md)、[docs/data-model.md](docs/data-model.md) 与 [CHANGELOG.md](CHANGELOG.md)，同步本次后台改密能力、接口契约、会话失效口径、验证方式和回滚说明

### 变更原因

- 当前后台登录后只支持继续访问内容管理、标签、任务、日志和审计页面，缺少管理员在已登录状态下自行修改密码的入口
- 这会导致管理员想更换后台口令时只能直接改库、重新初始化，或依赖额外脚本，不符合后台管理页的基本使用预期
- 因此需要在不改数据库结构、不重做后台认证体系的前提下，补一个保守的“已登录后修改自己的密码”页面和接口

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T16:33:08Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖后台认证 API、后台导航、后台登录后的账号安全操作，以及对应的集成测试和项目文档
- 管理员现在可以访问 `/admin/change-password`，输入当前密码和两次新密码完成改密；成功后需要使用新密码重新登录
- 本次采用更保守的安全口径：改密成功后会立即使该账号当前已有后台会话失效，避免旧会话继续可用
- 本次不包含管理员管理他人账号、密码强度策略升级、角色权限改造、数据库表结构调整或新的配置项

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_admin_auth.py tests/integration/test_admin_frontend.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除 `POST /api/admin/auth/change-password` 接口、回退 `/admin/change-password` 页面和对应测试文档，或执行 `git revert` 回退本次提交
- 回滚后后台将恢复为“只支持登录和登出，不支持登录后自助修改密码”的状态

## 2026-03-27T16:02:25Z

### 变更内容

- 更新 [Makefile](Makefile)，把 `make run` 从固定监听 `127.0.0.1:8000` 调整为跟随 `.env` / 环境变量中的 `BINGWALL_APP_HOST` 与 `BINGWALL_APP_PORT`
- 更新 [.env.example](.env.example) 与 [README.md](README.md)，把本地默认端口和所有运行示例统一为 `30003`
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md) 与 [CHANGELOG.md](CHANGELOG.md)，记录本次启动端口修正、验证方式、影响范围与回滚说明

### 变更原因

- 当前仓库的 `.env` 已配置 `BINGWALL_APP_PORT=30003`，但 `make run` 仍硬编码为 `8000`
- 这会导致服务实际监听端口、应用配置日志和文档说明三者不一致，容易让操作者误判服务是否启动成功
- 因此需要优先修正启动入口，让运行行为与配置文件保持一致

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T16:02:25Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖本地启动命令、环境变量示例和 README 里的访问示例端口
- 在当前 `.env` 下，`make run` 启动后会监听 `0.0.0.0:30003`
- 本次不包含接口字段调整、业务逻辑改造、部署拓扑调整或数据库结构修改

### 验证步骤

- 停止原先监听 `8000` 的开发服务
- 执行 `make run`
- 执行 `curl http://127.0.0.1:30003/api/health/live`
- 执行 `curl http://127.0.0.1:30003/api/health/ready`

### 回滚说明

- 如需回滚本次变更，可把 [Makefile](Makefile) 的 `run` 命令改回固定 `8000`，并回退 `.env.example`、`README.md`、`PROJECT_STATE.md` 与 [CHANGELOG.md](CHANGELOG.md) 的同步说明，或执行 `git revert` 回退本次提交
- 回滚后若 `.env` 仍声明 `30003`，启动行为和配置文档将再次出现不一致

## 2026-03-27T15:20:06Z

### 变更内容

- 更新 [app/api/admin/routes.py](app/api/admin/routes.py)、[app/services/admin_collection.py](app/services/admin_collection.py)、[app/repositories/collection_repository.py](app/repositories/collection_repository.py) 与 [app/schemas/admin_collection.py](app/schemas/admin_collection.py)，新增 `POST /api/admin/collection-tasks/{task_id}/consume` 后台接口，允许管理员手动执行指定的 `queued` 采集任务，并补齐对应审计日志
- 更新 [web/admin/assets/admin.js](web/admin/assets/admin.js)，在后台采集任务列表页和详情页新增“立即执行”按钮，并把页面说明从“只观察 cron 消费”调整为“既支持 cron，也支持人工触发 queued 任务”
- 更新 [tests/integration/test_admin_collection.py](tests/integration/test_admin_collection.py) 与 [tests/integration/test_admin_frontend.py](tests/integration/test_admin_frontend.py)，补齐后台手动触发成功、非 `queued` 状态拒绝和前端资源接线断言
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md) 与 [CHANGELOG.md](CHANGELOG.md)，同步本次手动触发能力、验证方式、影响范围和回滚说明

### 变更原因

- 当前后台“采集任务”页只能创建 `queued` 任务、查看状态和重试失败任务，缺少管理员立即执行指定排队任务的入口
- 这会让后台页面在没有现成 `cron` 消费或需要人工补跑时，无法完成真正意义上的“手动触发”
- 因此需要在不移除既有 `cron` 模式的前提下，为单个 `queued` 任务补一个受控、可审计的人工触发入口

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T15:20:06Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖后台采集任务 API、后台任务页面交互、采集任务执行状态流转和审计日志记录
- 管理员现在可以在 `/admin/tasks` 列表页或任务详情页直接触发指定 `queued` 任务执行；现有 `cron` 消费入口仍然保留
- 为避免并发冲突，非 `queued` 任务仍会被拒绝手动触发；同来源已有运行中任务时，也会拒绝本次人工触发
- 本次不包含数据库表结构修改、来源采集规则调整、调度系统替换或自动改造为“创建即执行”

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_admin_collection.py tests/integration/test_admin_frontend.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除 `POST /api/admin/collection-tasks/{task_id}/consume` 接口、回退后台页面按钮与相关测试文档，或执行 `git revert` 回退本次提交
- 回滚后后台会恢复为“只能创建 queued 任务，再等待 cron 或命令行消费”的状态

## 2026-03-27T14:47:30Z

### 变更内容

- 更新 [app/repositories/sqlite.py](app/repositories/sqlite.py)，把 SQLite 连接创建统一调整为 `check_same_thread=False`，兼容 FastAPI 同步依赖与同步路由在同一请求内跨工作线程执行的情况
- 新增 [tests/unit/test_sqlite.py](tests/unit/test_sqlite.py)，补齐跨线程查询回归测试和外键约束开启断言
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md)、[CHANGELOG.md](CHANGELOG.md) 与 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)，同步本次公开接口 `500` 的根因、影响范围、验证方式与回滚说明

### 变更原因

- 列表页显示“服务繁忙”并不是页面重试逻辑失效，而是公开接口在查询 SQLite 时直接报 `500`
- 根因是仓库层数据库连接在一个线程里创建，却在另一个线程里执行查询；SQLite 默认禁止这种跨线程使用
- 因此需要在不改业务查询逻辑的前提下，先把连接层修正为兼容当前 FastAPI 执行模型

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T14:47:30Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖所有通过 [app/repositories/sqlite.py](app/repositories/sqlite.py) 创建 SQLite 连接的仓库
- 用户侧直接改善的是公开列表、公开筛选项等接口不再因线程限制而返回 `500`
- 本次不包含接口字段调整、前端页面改版、数据库表结构修改或部署方式调整

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/unit/test_sqlite.py tests/integration/test_public_api.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`
- 启动服务后执行 `curl http://127.0.0.1:30003/api/public/wallpapers?page=1&page_size=6&sort=date_desc`

### 回滚说明

- 如需回滚本次变更，可把 [app/repositories/sqlite.py](app/repositories/sqlite.py) 的连接参数恢复为默认值，并回退对应测试和文档更新，或执行 `git revert` 回退本次提交
- 回滚后若仍保留当前 FastAPI 同步依赖写法，公开接口可能再次出现跨线程访问 SQLite 导致的 `500`

## 2026-03-27T14:24:40Z

### 变更内容

- 更新 [app/core/config.py](app/core/config.py)、[app/services/source_collection.py](app/services/source_collection.py)、[app/services/bing_collection.py](app/services/bing_collection.py) 与 [app/repositories/collection_repository.py](app/repositories/collection_repository.py)，新增 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED` 配置，并让新采集内容在资源全部就绪后默认自动切到 `enabled + is_public=true`
- 更新 [app/collectors/bing.py](app/collectors/bing.py)、[app/collectors/nasa_apod.py](app/collectors/nasa_apod.py) 与 [app/collectors/manual_tasks.py](app/collectors/manual_tasks.py)，让 Bing、NASA APOD 和手动任务消费三条采集入口都使用同一自动公开策略
- 更新 [tests/integration/test_bing_collection_service.py](tests/integration/test_bing_collection_service.py)、[tests/integration/test_multi_source_collection.py](tests/integration/test_multi_source_collection.py)、[tests/integration/test_admin_collection.py](tests/integration/test_admin_collection.py) 与 [tests/unit/test_config.py](tests/unit/test_config.py)，补齐默认自动公开、关闭自动公开后保持 `draft` 和配置加载验证
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/system-design.md](docs/system-design.md)、[docs/data-model.md](docs/data-model.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md)、[docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)、[.env.example](.env.example) 与 [deploy/systemd/bingwall.env.example](deploy/systemd/bingwall.env.example)，同步默认自动公开口径、关闭方式和排障说明

### 变更原因

- 当前采集链路会先把新内容写成 `draft + is_public=0`，导致采集成功后公开 API 仍然返回空列表，必须再手工改库才能看到内容
- 直接把入库默认值改成 `enabled` 不可行，因为数据库约束要求 `enabled` 必须搭配 `resource_status = ready`
- 因此需要在资源全部就绪后再自动公开，并保留一个可关闭的配置开关，兼顾当前需求和后续回退到人工审核的可能性

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 新增配置项：`BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED`
- 变更时间：`2026-03-27T14:24:40Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖 Bing、NASA APOD、手动任务消费三条采集入口，以及相关测试与文档
- 当前默认配置下，新采集内容会在原图、缩略图、预览图和下载图全部就绪后自动切到 `enabled` 且 `is_public = true`
- 当 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED=false` 时，新采集内容仍保持 `draft`，沿用人工审核后再发布的旧流程
- 本次不包含历史 `draft` 数据批量发布、后台页面改造、公开前端筛选改造或数据库表结构调整

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_bing_collection_service.py tests/integration/test_multi_source_collection.py tests/integration/test_admin_collection.py tests/unit/test_config.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除自动公开配置和资源就绪后的自动发布接线、回退相关测试与文档更新，或执行 `git revert` 回退本次提交
- 回滚后仓库将恢复到“新采集内容默认保持 draft，需要后台或手工改库后才会公开显示”的状态

## 2026-03-27T13:41:00Z

### 变更内容

- 新增 [app/repositories/migrations/versions/V0006__admin_user_status_constraint.sql](app/repositories/migrations/versions/V0006__admin_user_status_constraint.sql)，在迁移阶段先清洗 `admin_users.status` 的 legacy 数据，再通过数据库触发器拦截新的非法状态写入
- 更新 [tests/integration/test_sqlite_migrations.py](tests/integration/test_sqlite_migrations.py)，补齐第 `6` 个迁移版本、触发器存在性断言，以及 legacy `active` / 非法状态清洗和迁移后非法写入拦截测试
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md)、[docs/data-model.md](docs/data-model.md) 与 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)，同步管理员状态枚举、legacy 值迁移口径和最新排障建议

### 变更原因

- 当前管理员登录只在业务代码里接受 `status = enabled`，但数据库表结构仍允许写入任意文本状态，`active`、大小写变体或其他脏值会直到登录时报错才暴露
- 既然这类问题已经在真实排障中出现过，就需要把约束下沉到数据库层，避免未来继续写入非法状态
- 对已有环境必须先兼容性清洗再施加约束，避免升级时因为历史脏数据直接中断迁移

### 依赖变更

- 无新增第三方依赖
- 新增数据库迁移：`V0006__admin_user_status_constraint.sql`
- 变更时间：`2026-03-27T13:41:00Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖 SQLite 迁移链路、迁移测试、管理员状态字段说明和排障文档
- `admin_users.status` 现在只允许 `enabled`、`disabled`；历史 `active` 会在迁移时归一化为 `enabled`，其他未知非法值会保守降级为 `disabled`
- 迁移完成后，无论是插入还是更新，数据库都会拒绝新的非法管理员状态写入
- 本次不包含管理员角色扩展、登录错误文案调整、后台页面改造或会话表结构调整

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_sqlite_migrations.py tests/integration/test_admin_bootstrap.py tests/integration/test_admin_auth.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除 `V0006__admin_user_status_constraint.sql`、回退迁移测试与文档更新，或执行 `git revert` 回退本次提交
- 需要注意：如果某个环境已经执行了本次迁移，历史非法状态可能已被归一化为 `enabled` 或 `disabled`；代码回滚不会自动恢复这些清洗前的原始值

## 2026-03-27T13:36:36Z

### 变更内容

- 更新 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)，删除“默认账号信息”表，避免再暗示仓库存在固定的 `admin/admin123` 默认后台账号
- 同步把后台登录示例改成基于 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 的占位写法，并要求调用方填写自己初始化时设置的管理员密码

### 变更原因

- 当前实际实现并没有硬编码默认管理员密码；管理员账号只会在初始化前提供环境变量时按配置创建
- 排障文档此前一边说明“未生成管理员账号会导致无法登录”，一边又给出 `admin/admin123`，会把操作者带到错误路径，也会误导读者以为仓库内置弱口令

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T13:36:36Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围仅限排障文档，不涉及业务代码、接口行为、数据库结构或测试逻辑
- 文档现在明确：后台登录应使用初始化时配置的管理员用户名和密码，而不是假定存在仓库默认账号

### 验证步骤

- 人工核对 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md) 中“问题 8 / 9”“验证运行”与“注意事项”三处描述保持一致，不再出现 `admin123` 或“默认账号信息”表

### 回滚说明

- 如需回滚本次变更，可恢复 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md) 与 [CHANGELOG.md](CHANGELOG.md) 的本次文档修订，或执行 `git revert` 回退本次提交
- 本次仅为文档修正，回滚不涉及代码或数据回滚

## 2026-03-27T13:31:19Z

### 变更内容

- 更新 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)，把“日期范围筛选 API”从待开发占位描述改为已实现说明，补齐闭区间语义、统一 `422` 参数错误行为，以及“当前未扩展公开前端日期选择器”的范围说明

### 变更原因

- 上一轮功能已完成代码、测试和主文档同步，但遗漏了排障文档中的同名条目，导致该文件仍显示“待开发”，与实际实现状态不一致
- 该文件还保留了“更新前端页面支持日期选择器”的计划描述，容易让读者误以为这次已经改了前端筛选界面

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T13:31:19Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围仅限排障与搭建文档，不涉及业务代码、接口行为、数据库结构、测试逻辑或前端页面
- 文档现在明确：`date_from` / `date_to` 已可用、按 `wallpaper_date` 做闭区间过滤，且参数倒置时会返回统一 `422 COMMON_INVALID_ARGUMENT`

### 验证步骤

- 人工核对 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md) 中“日期范围筛选 API”条目与 [README.md](README.md)、[docs/api-conventions.md](docs/api-conventions.md) 的公开列表参数说明一致

### 回滚说明

- 如需回滚本次变更，可恢复 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md) 与 [CHANGELOG.md](CHANGELOG.md) 的本次文档修订，或执行 `git revert` 回退本次提交
- 本次仅为文档修正，回滚不涉及代码或数据回滚

## 2026-03-27T13:21:12Z

### 变更内容

- 更新 [app/schemas/public.py](app/schemas/public.py)、[app/repositories/public_repository.py](app/repositories/public_repository.py)、[app/api/public/routes.py](app/api/public/routes.py)、[app/api/errors.py](app/api/errors.py) 与 [app/main.py](app/main.py)，为 `GET /api/public/wallpapers` 新增 `date_from`、`date_to` 两个公开查询参数，格式固定为 `YYYY-MM-DD`，并按 `wallpaper_date` 执行包含开始日和结束日的日期范围过滤；同时补齐依赖参数模型校验失败时的统一 `422` 错误响应接线
- 更新 [tests/integration/test_public_api.py](tests/integration/test_public_api.py)，补齐公开列表日期范围命中、起止日期倒置校验失败和非法日期格式校验失败的集成测试
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md) 与 [docs/api-conventions.md](docs/api-conventions.md)，同步公开列表新参数、闭区间语义、示例请求和项目状态说明

### 变更原因

- 当前公开 API 列表已支持关键词、标签、地区和分辨率筛选，但缺少最基础的按日期范围筛选能力，调用方需要自行拉全量后再二次过滤
- 本次保持最保守范围，只在现有公开列表链路上增加两个只读查询参数，不调整数据库结构、不改前端页面、不改后台接口
- 需要让调用方能直接按壁纸日期做归档浏览、区间拉取和历史同步，同时继续复用现有分页、公开可见性和统一错误响应约定

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T13:21:12Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖公开列表查询参数校验、公开仓储 SQL 条件、公开 API 集成测试和相关说明文档
- `/api/public/wallpapers` 现在支持 `date_from` 与 `date_to`，两者基于 `wallpaper_date` 做闭区间过滤，并且可以与 `keyword`、`tag_keys`、地区、分辨率、排序和分页组合使用
- 当两个日期参数同时提供且 `date_to < date_from`，接口会继续返回统一的 `422 COMMON_INVALID_ARGUMENT` 参数错误响应
- 本次不包含数据库表结构调整、后台内容列表日期筛选变更、公开前端筛选表单改造或 `today` / `random` 端点行为调整

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_public_api.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除公开列表新增的日期参数、回退仓储筛选条件、测试和文档更新，或执行 `git revert` 回退本次提交
- 回滚后仓库将恢复到“公开列表仅支持关键词、标签、地区和分辨率筛选，不支持按壁纸日期范围筛选”的状态
- 本次未引入数据库迁移，因此代码回滚不涉及数据回滚动作

## 2026-03-27T12:52:50Z

### 变更内容

- 更新 [app/api/public/routes.py](app/api/public/routes.py)、[app/services/public_catalog.py](app/services/public_catalog.py) 与 [app/repositories/public_repository.py](app/repositories/public_repository.py)，新增 `GET /api/public/wallpapers/today` 和 `GET /api/public/wallpapers/random` 两个公开端点，并复用现有公开详情的字段结构、资源 URL 生成逻辑和统一 404 错误响应
- 更新 [tests/integration/test_public_api.py](tests/integration/test_public_api.py)，补齐今日壁纸默认市场优先、默认市场缺失回退、公开可见性过滤、随机抽取仅限公开可见内容、OSS 资源地址返回和空结果 404 等集成测试
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)，同步新增公开接口、UTC 日期语义、随机池范围、最小验证命令和排障说明

### 变更原因

- 当前公开 API 已有列表、详情和下载登记，但缺少“站点今日壁纸”和“随机壁纸”这两个更直接的读取入口，调用方需要自己额外做筛选或随机逻辑
- 本次保持最保守范围，只在现有公开查询链路上补两个只读端点，不改数据库结构、不改前端页面、不改下载链路
- 需要保证新接口与既有公开详情完全一致，避免调用方拿到不同字段结构或随机到不可公开访问的数据

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T12:52:50Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖公开 API 查询链路、公开 API 集成测试和相关说明文档
- `/api/public/wallpapers/today` 现在按 UTC 当天匹配 `wallpaper_date`，并在当天存在多条候选时优先返回站点默认市场内容
- `/api/public/wallpapers/random` 现在仅从当前公开可见内容中随机选取，避免随机到详情不可访问的记录
- 本次不包含数据库表结构调整、公开前端页面改造、后台管理能力扩展或自动发布策略调整

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/integration/test_public_api.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除两个新增公开端点、回退公开仓库查询与测试、恢复相关文档描述，或执行 `git revert` 回退本次提交
- 回滚后仓库将恢复到“公开端仅提供列表、详情、筛选项、标签、站点信息和下载登记接口”的状态，依赖 `today` / `random` 的调用方需要自行切换回旧方案
- 本次未引入数据库迁移，因此代码回滚不涉及数据回滚动作
## 2026-03-27T12:36:54Z

### 变更内容

- 新增 [app/services/admin_bootstrap.py](app/services/admin_bootstrap.py)，实现首个管理员账号幂等初始化：仅当 `admin_users` 为空且提供了初始化凭据时，自动创建状态为 `enabled` 的 `super_admin`
- 更新 [app/core/config.py](app/core/config.py) 与 [app/repositories/migrations/__main__.py](app/repositories/migrations/__main__.py)，新增 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME`、`BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD` 配置校验，并把管理员初始化接入数据库迁移命令
- 新增 [tests/integration/test_admin_bootstrap.py](tests/integration/test_admin_bootstrap.py)，并更新 [tests/unit/test_config.py](tests/unit/test_config.py) 与 [tests/conftest.py](tests/conftest.py)，覆盖首次创建、重复执行不重复创建、已有管理员不覆盖，以及配置成对出现和密码长度校验
- 更新 [.env.example](.env.example)、[deploy/systemd/bingwall.env.example](deploy/systemd/bingwall.env.example)、[README.md](README.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md)、[docs/setup-troubleshooting.md](docs/setup-troubleshooting.md) 与 [PROJECT_STATE.md](PROJECT_STATE.md)，同步默认管理员初始化方式、使用步骤和排障说明

### 变更原因

- 当前后台登录依赖 `admin_users` 表，但仓库原先只能手工写 SQL 创建管理员，首次搭建和部署时容易漏掉这一步
- 直接把一个真实可用的默认密码硬编码进仓库会形成已知弱口令，因此本次采用“环境变量提供初始化凭据 + 首次初始化时写入数据库”的保守方案
- 需要保证初始化动作可重复执行，且在已有管理员时不覆盖现有账号，避免对既有环境造成误改

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 新增可选配置项：`BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME`、`BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`
- 变更时间：`2026-03-27T12:36:54Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖数据库初始化命令、管理员首个账号创建流程、环境变量示例、部署说明和排障文档
- 当 `admin_users` 为空且同时提供初始化用户名和密码时，执行 `make db-migrate` 会自动创建一个启用中的 `super_admin`
- 当数据库中已经存在管理员时，再次执行初始化不会覆盖已有账号，也不会重复创建默认管理员
- 本次不包含后台角色体系扩展、管理员修改密码界面、密码轮换流程或数据库表结构调整

### 验证步骤

- 执行 `./.venv/bin/python -m pytest tests/unit/test_config.py tests/integration/test_admin_bootstrap.py tests/integration/test_admin_auth.py`
- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py scripts/run_backup.py scripts/run_restore.py scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除管理员初始化服务与配置校验、回退迁移命令接线、测试和文档更新，或执行 `git revert` 回退本次提交
- 若某个环境已经通过该机制创建了首个管理员账号，代码回滚不会自动删除该账号；如需完全回退初始化结果，应先人工删除对应 `admin_users` 记录并确认相关会话与审计影响

## 2026-03-27T12:19:30Z

### 变更内容

- 更新 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)，修正文档中对 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 的说明，明确“未设置”与“设置为空字符串”在当前配置模型中的行为差异
- 同步调整 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md) 的完整搭建步骤与注意事项，改为区分“仅本地文件存储”和“启用 OSS / CDN 公网访问”两种配置方式
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md)，记录该排障结论已沉淀进项目文档，并刷新文档元信息时间

### 变更原因

- 服务器实测部署中已确认：`BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=` 会被解析为空字符串并触发 `pydantic` URL 校验失败，但该变量在仅本地存储场景下本来允许完全不设置
- 原文把“删掉变量”和“填一个临时占位值”混在一起，容易让部署人员误以为生产环境必须长期保留 `http://localhost` 之类的占位地址
- 该变量还会参与 `storage_backend = oss` 资源的真实公网 URL 拼接，因此文档需要明确它不是单纯的启动占位参数

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移、锁文件或运行时版本变更
- 变更时间：`2026-03-27T12:19:30Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围限于部署与排障文档，不涉及业务代码、接口契约、数据库结构或部署模板行为变更
- 后续部署人员在仅使用本地文件存储时，可直接不设置该变量；在启用 OSS / CDN 时，必须填写真实公网地址前缀
- 本次不包含配置模型修改、`.env.example` 模板改造或资源定位逻辑调整

### 验证步骤

- 重新检查 [app/core/config.py](app/core/config.py) 中 `storage_oss_public_base_url: AnyHttpUrl | None = None` 的配置定义
- 重新检查 [app/services/resource_locator.py](app/services/resource_locator.py) 中 `storage_backend = oss` 时对 `oss_public_base_url` 的实际使用逻辑
- 使用 `./.venv/bin/python` 实测验证：变量缺失时加载结果为 `None`；变量设置为空字符串时触发 `ValidationError`

### 回滚说明

- 如需回滚本次变更，可回退 [docs/setup-troubleshooting.md](docs/setup-troubleshooting.md)、[CHANGELOG.md](CHANGELOG.md) 与 [PROJECT_STATE.md](PROJECT_STATE.md) 的文档修订
- 回滚后文档将恢复到“默认建议填写 `http://localhost` 占位值”的旧表述，部署人员可能继续混淆“未设置”和“空字符串”的差别

## 2026-03-26T15:13:37Z

### 变更内容

- 更新 [app/schemas/public.py](app/schemas/public.py)、[app/schemas/admin_content.py](app/schemas/admin_content.py)、[app/repositories/public_repository.py](app/repositories/public_repository.py)、[app/repositories/admin_content_repository.py](app/repositories/admin_content_repository.py)、[app/api/public/routes.py](app/api/public/routes.py) 与 [app/api/admin/routes.py](app/api/admin/routes.py)，为公开列表和后台内容列表新增 `keyword` 参数，并把标题、简述、版权说明、描述和标签接入关键词匹配
- 更新 [web/public/assets/site.js](web/public/assets/site.js) 与 [web/admin/assets/admin.js](web/admin/assets/admin.js)，为 `/wallpapers` 和 `/admin/wallpapers` 新增关键词输入框，支持与现有筛选条件组合查询，且继续只通过既有 API 取数
- 更新 [tests/integration/test_public_api.py](tests/integration/test_public_api.py)、[tests/integration/test_admin_content.py](tests/integration/test_admin_content.py)、[tests/integration/test_public_frontend.py](tests/integration/test_public_frontend.py) 与 [tests/integration/test_admin_frontend.py](tests/integration/test_admin_frontend.py)，覆盖公开搜索、后台联合检索、前后台结果差异解释、页面资产引用和代表性样本响应时间验证
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/data-model.md](docs/data-model.md)，同步 `T3.6` 完成状态、搜索字段口径、验证样本与后续优先级

### 变更原因

- 完成阶段三 `T3.6`，把“在现有筛选基础上增加关键词搜索，并保持公开 / 后台状态规则可解释”的设计要求推进为可运行实现
- 保持最保守范围，继续复用现有 FastAPI、SQLite、原生前端与现有列表接口，不引入全文检索引擎、新依赖或数据库结构变更
- 让公开端和后台端共享同一组关键词来源，同时保留各自既有状态过滤规则，避免搜索结果口径割裂

### 依赖变更

- 无新增第三方依赖
- 无数据库迁移或锁文件变更
- 变更时间：`2026-03-26T15:13:37Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖公开列表接口、后台内容列表接口、公开列表页、后台内容管理页、关键词搜索测试与相关文档
- 公开列表现在支持 `keyword` 与 `market_code`、`tag_keys`、分辨率条件组合查询；后台内容列表现在支持 `keyword` 与内容状态、资源状态、地区、创建时间联合检索
- 当前关键词搜索口径为标题、简述、版权说明、描述和标签，其中公开端只匹配启用标签，后台端保留全部已绑定标签匹配能力
- 本次不包含全文检索引擎接入、搜索高亮、联想提示、独立搜索接口或数据库结构调整

### 验证步骤

- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m pytest tests/integration/test_public_api.py tests/integration/test_admin_content.py tests/integration/test_public_frontend.py tests/integration/test_admin_frontend.py`
- 代表性样本响应时间记录：30 条样本下，公开搜索 `keyword=Benchmark` 本地实测约 `0.0043` 秒；后台搜索 `keyword=Benchmark` 本地实测约 `0.0058` 秒

### 回滚说明

- 如需回滚本次变更，可删除公开 / 后台列表的 `keyword` 参数、回退 repository 查询条件、前后台页面输入框、测试与文档更新，或执行 `git revert` 回退本次提交
- 回滚后仓库将恢复到“仅支持结构化筛选和标签筛选、不支持关键词搜索、`T3.6` 仍停留在文档预留状态”的状态

## 2026-03-26T14:38:59Z

### 变更内容

- 新增 [app/repositories/migrations/versions/V0005__download_events.sql](app/repositories/migrations/versions/V0005__download_events.sql)、[app/repositories/download_repository.py](app/repositories/download_repository.py)、[app/services/downloads.py](app/services/downloads.py) 与 [app/schemas/admin_downloads.py](app/schemas/admin_downloads.py)，落地下载登记表、公开下载目标解析、后台下载统计聚合和对应 schema
- 更新 [app/api/public/routes.py](app/api/public/routes.py)、[app/api/admin/routes.py](app/api/admin/routes.py)、[app/schemas/public.py](app/schemas/public.py)、[app/web/routes.py](app/web/routes.py)、[web/public/assets/site.js](web/public/assets/site.js) 与 [web/admin/assets/admin.js](web/admin/assets/admin.js)，新增 `POST /api/public/download-events`、`GET /api/admin/download-stats`、`/admin/download-stats`，并把公开详情页下载按钮改为“先登记，再跳转静态资源”
- 更新 [tests/integration/test_sqlite_migrations.py](tests/integration/test_sqlite_migrations.py)、[tests/integration/test_public_api.py](tests/integration/test_public_api.py)、[tests/integration/test_download_statistics.py](tests/integration/test_download_statistics.py)、[tests/integration/test_admin_frontend.py](tests/integration/test_admin_frontend.py) 与 [tests/integration/test_public_frontend.py](tests/integration/test_public_frontend.py)，覆盖迁移、公开下载登记、后台统计接口以及前后台页面壳引用
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/data-model.md](docs/data-model.md) 与 [docs/api-conventions.md](docs/api-conventions.md)，同步 `T3.5` 完成状态、接口契约、数据字段、验证方式和后续优先级

### 变更原因

- 完成阶段三 `T3.5`，把“下载登记 + 后台趋势统计”的设计约束推进为可运行实现
- 继续保持最保守范围，复用现有 FastAPI、SQLite、原生前端和静态资源链路，不让应用服务承担大文件主传输
- 让下载行为可追踪、可聚合、可在后台观测，同时保留 `T3.4` 已有的本地与 OSS / CDN 静态资源兼容能力

### 依赖变更

- 无新增第三方依赖
- 新增数据库迁移：`V0005__download_events.sql`
- 变更时间：`2026-03-26T14:38:59Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖公开详情下载按钮行为、下载登记落库、后台下载统计接口与页面、迁移校验和相关文档
- 公开下载现在先通过 `/api/public/download-events` 登记，再跳转到 `/images/*` 或 OSS / CDN 静态资源地址；真实文件传输主流量仍不经过应用服务
- 后台现在可通过 `/api/admin/download-stats` 和 `/admin/download-stats` 查看最近 7 / 30 / 90 天的总量、热门内容和按日趋势
- 本次不包含 Nginx 下载日志采集、对象存储上传、地区偏好分析、来源对比分析或搜索能力实现

### 验证步骤

- 执行 `./.venv/bin/python -m ruff check app tests`
- 执行 `./.venv/bin/python -m pytest tests/integration/test_sqlite_migrations.py tests/integration/test_public_api.py tests/integration/test_download_statistics.py tests/integration/test_admin_frontend.py tests/integration/test_public_frontend.py`
- 执行 `make format`
- 执行 `make verify`

### 回滚说明

- 如需回滚本次变更，可删除下载登记迁移、下载 repository / service / schema、公开和后台统计接口、前后台页面接入与相关测试，或执行 `git revert` 回退本次提交
- 若环境中已经写入 `download_events` 数据，回滚前应确认是否需要保留这些统计明细，避免清理后丢失已观测到的下载趋势数据
- 回滚后仓库将恢复到“公开详情直接给出静态下载地址、后台尚未提供下载统计、`T3.5` 仍停留在设计预留状态”的状态

## 2026-03-26T14:04:36Z

### 变更内容

- 新增 [app/services/resource_locator.py](app/services/resource_locator.py)，把资源定位从固定 `/images/<relative_path>` 抽象为统一定位器，支持 `storage_backend = local` 与 `storage_backend = oss` 两类地址生成，并对相对路径做越界校验
- 更新 [app/core/config.py](app/core/config.py)、[app/api/public/routes.py](app/api/public/routes.py)、[app/api/admin/routes.py](app/api/admin/routes.py)、[app/services/public_catalog.py](app/services/public_catalog.py)、[app/services/admin_content.py](app/services/admin_content.py)、[app/repositories/public_repository.py](app/repositories/public_repository.py) 与 [app/repositories/admin_content_repository.py](app/repositories/admin_content_repository.py)，让公开列表、公开详情、后台列表和后台详情按资源记录中的 `storage_backend` 生成本地或 OSS / CDN 地址
- 更新 [.env.example](.env.example)、[deploy/systemd/bingwall.env.example](deploy/systemd/bingwall.env.example)、[README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/data-model.md](docs/data-model.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/deployment-runbook.md](docs/deployment-runbook.md)，补齐 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 配置、迁移期目录语义、备份边界和 `T3.4` 完成状态
- 新增 [tests/unit/test_resource_locator.py](tests/unit/test_resource_locator.py)，并更新 [tests/unit/test_config.py](tests/unit/test_config.py)、[tests/integration/test_public_api.py](tests/integration/test_public_api.py)、[tests/integration/test_admin_content.py](tests/integration/test_admin_content.py) 与 [tests/integration/test_admin_auth.py](tests/integration/test_admin_auth.py)，覆盖本地 / OSS 地址生成、配置加载、公开接口并存访问和后台接口兼容

### 变更原因

- 完成阶段三 `T3.4`，把“资源定位兼容本地与 OSS/CDN、迁移期允许新旧资源共存”的设计要求推进为可运行实现
- 保持最保守范围，只抽象资源定位和公开地址生成，不提前引入对象存储 SDK、不改现有本地下载入库链路、不改变 Nginx `/images/` 本地服务方式
- 确保历史本地资源继续可访问，同时为后续逐步把资源切到 OSS / CDN 留出稳定接口

### 依赖变更

- 无新增第三方依赖
- 新增配置项：`BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL`
- 变更时间：`2026-03-26T14:04:36Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖公开列表、公开详情、后台内容列表、后台内容详情、配置加载、部署文档和相关测试
- `storage_backend = local` 的资源继续走 `/images/<relative_path>`；`storage_backend = oss` 的资源改为返回配置好的绝对公网地址
- 本次不包含对象存储上传、对象存储 SDK 接入、CDN 刷新、备份导出 OSS 对象或 Nginx 配置结构变更

### 验证步骤

- 执行 `make format`
- 执行 `make verify`

### 回滚说明

- 如需回滚本次变更，可删除统一资源定位器，回退公开 / 后台接口的资源 URL 生成逻辑、配置项、测试与文档更新，或执行 `git revert` 回退本次提交
- 若环境中已经写入 `storage_backend = oss` 的资源记录，回滚前应先确认是否需要把这些记录改回 `local` 或暂停公开访问，避免代码回退后仍存在无法生成地址的资源记录
- 回滚后仓库将恢复到“公开与后台资源地址固定指向本地 `/images/`、`T3.4` 仍停留在设计预留状态”的状态

## 2026-03-26T13:42:52Z

### 变更内容

- 新增 [app/services/image_variants.py](app/services/image_variants.py)、[app/domain/resource_variants.py](app/domain/resource_variants.py) 与 [app/repositories/migrations/versions/V0004__image_resource_variants.sql](app/repositories/migrations/versions/V0004__image_resource_variants.sql)，把资源类型规范扩展为 `original` / `thumbnail` / `preview` / `download`，并为同一壁纸的资源类型增加唯一索引
- 更新 [app/services/source_collection.py](app/services/source_collection.py) 与 [app/repositories/collection_repository.py](app/repositories/collection_repository.py)，让采集链路在原图入库后生成缩略图、详情预览图和下载图，并把派生失败原因同步写入 `image_resources` 和任务日志
- 更新 [app/repositories/public_repository.py](app/repositories/public_repository.py) 与 [app/services/public_catalog.py](app/services/public_catalog.py)，让公开列表优先返回缩略图，公开详情区分预览图与下载图，并保留对历史仅原图数据的保守回退
- 更新 [app/repositories/health_repository.py](app/repositories/health_repository.py)，让资源状态同步与资源巡检按“原图 + 缩略图 + 预览图 + 可下载时的下载图”统一判断，避免派生资源失败后仍被误判为可公开
- 更新 [tests/integration/test_bing_collection_service.py](tests/integration/test_bing_collection_service.py)、[tests/integration/test_multi_source_collection.py](tests/integration/test_multi_source_collection.py)、[tests/integration/test_public_api.py](tests/integration/test_public_api.py)、[tests/integration/test_health_checks.py](tests/integration/test_health_checks.py)、[tests/integration/test_sqlite_migrations.py](tests/integration/test_sqlite_migrations.py) 与 [tests/support/image_factory.py](tests/support/image_factory.py)，覆盖派生资源生成、公开端资源选取、失败落盘与迁移校验
- 更新 [pyproject.toml](pyproject.toml)、[requirements.lock.txt](requirements.lock.txt)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/data-model.md](docs/data-model.md) 与 [docs/api-conventions.md](docs/api-conventions.md)，同步 `T3.3` 完成状态、依赖锁定、资源类型口径和公开接口约束

### 变更原因

- 完成阶段三 `T3.3`，把“资源派生版本预留”推进为可运行实现，补齐列表缩略图、详情预览图和下载图的真实资源链路
- 继续保持最保守范围，复用现有 FastAPI、SQLite、本地文件存储和公开前端，不提前引入 WebP、OSS/CDN、对象存储 SDK 或新的前端框架
- 让资源派生失败进入现有后台任务日志和资源状态闭环，避免列表页继续直接加载原图、也避免后台难以定位派生失败原因

### 依赖变更

- 新增直接依赖：`Pillow==12.1.1`
- 变更时间：`2026-03-26T13:42:52Z`
- 依赖类型：直接依赖

### 影响范围

- 影响范围覆盖采集入库、资源记录、公开列表与详情接口、资源状态联动、资源巡检和相关测试
- 新采集内容现在会生成 `original`、`thumbnail`、`preview`，以及可下载时的 `download` 资源；公开列表默认使用缩略图，详情区分预览图和下载图
- 历史仅有原图的既有数据，公开接口仍保留到原图的保守回退，避免升级后立即出现大量 404；但新资源状态判定已经按多版本资源完整性执行
- 不涉及 OSS/CDN、下载统计、搜索能力、部署拓扑变化或运行命令调整

### 验证步骤

- 执行 `make format`
- 执行 `make verify`

### 回滚说明

- 如需回滚本次变更，可删除资源派生处理模块、回退 `V0004__image_resource_variants.sql`、公开资源选取逻辑、相关测试与文档更新，或执行 `git revert` 回退本次提交
- 若目标环境已经采集出 `thumbnail` / `preview` / `download` 资源记录和对应文件，回滚前应确认是否需要保留这些派生文件，避免代码回退后磁盘残留未被引用的资源
- 回滚后仓库将恢复到“公开列表和详情均主要依赖单一原图资源、`T3.3` 仍停留在文档预留状态”的状态

## 2026-03-26T12:57:06Z

### 变更内容

- 新增 [app/services/source_collection.py](app/services/source_collection.py) 与 [app/domain/collection_sources.py](app/domain/collection_sources.py)，把采集执行链路抽象为按 `source_type` 分发的统一来源接口，并补齐跨来源任务认领逻辑
- 新增 [app/collectors/nasa_apod.py](app/collectors/nasa_apod.py)，并更新 [app/collectors/manual_tasks.py](app/collectors/manual_tasks.py)、[app/services/bing_collection.py](app/services/bing_collection.py)、[app/repositories/collection_repository.py](app/repositories/collection_repository.py) 与 [app/core/config.py](app/core/config.py)，接入 `nasa_apod` 作为 Bing 之外的新来源，同时保留 Bing 主链路兼容
- 更新 [app/schemas/admin_collection.py](app/schemas/admin_collection.py)、[app/services/admin_collection.py](app/services/admin_collection.py) 与 [app/api/admin/routes.py](app/api/admin/routes.py)，让后台任务创建、重试、任务消费和来源开关校验支持 `bing` / `nasa_apod`
- 更新 [web/admin/assets/admin.js](web/admin/assets/admin.js)、[Makefile](Makefile) 与 [.env.example](.env.example)，补齐后台来源选项、新的手动采集入口 `make collect-nasa-apod` 和 `BINGWALL_COLLECT_NASA_APOD_*` 配置示例
- 新增 [tests/integration/test_multi_source_collection.py](tests/integration/test_multi_source_collection.py)，并更新 [tests/integration/test_admin_collection.py](tests/integration/test_admin_collection.py)，覆盖 NASA APOD 新来源入库、后台任务创建/消费与来源日志区分；同时保留既有 Bing 集成测试验证不回归
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/data-model.md](docs/data-model.md)，同步 `T3.2` 完成状态、接口约束、配置入口和后续优先级

### 变更原因

- 完成阶段三 `T3.2`，把“多来源采集预留”推进为可运行实现，并确保 Bing 现有采集、去重和资源入库链路不回归
- 保持最保守范围，继续复用现有 SQLite、FastAPI、原生后台页面和本地文件存储，不引入消息队列、第三方 SDK 或新的前端框架
- 选择 `nasa_apod` 作为首个 Bing 之外的新来源，是因为其“一日一图”模型最贴合当前 `source_type + wallpaper_date + market_code` 唯一键约束，可在不改表结构的前提下安全落地

### 依赖变更

- 无新增第三方依赖
- 新增运行入口：`make collect-nasa-apod`
- 新增配置项：`BINGWALL_COLLECT_NASA_APOD_ENABLED`、`BINGWALL_COLLECT_NASA_APOD_DEFAULT_MARKET`、`BINGWALL_COLLECT_NASA_APOD_API_KEY`、`BINGWALL_COLLECT_NASA_APOD_TIMEOUT_SECONDS`、`BINGWALL_COLLECT_NASA_APOD_MAX_DOWNLOAD_RETRIES`
- 变更时间：`2026-03-26T12:57:06Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖采集服务抽象、来源配置、后台手动任务来源选择、任务消费分发、结构化日志和多来源测试
- 当前已支持 `bing` 与 `nasa_apod` 两种来源，其中 `nasa_apod` 的 `market_code` 固定为 `global`
- Bing 既有 CLI 入口、后台任务接口、去重规则和资源落库规则保持不变；新增来源沿用同一套资源入库和状态联动逻辑
- 不涉及数据库表结构调整、公开接口字段扩展、资源派生版本、OSS/CDN、下载统计或部署拓扑变化

### 验证步骤

- 执行 `make format`
- 执行 `./.venv/bin/python -m pytest tests/integration/test_bing_collection_service.py tests/integration/test_multi_source_collection.py tests/integration/test_admin_collection.py`
- 执行 `make verify`

### 回滚说明

- 如需回滚本次变更，可删除统一来源抽象、`nasa_apod` 采集适配器、后台来源选项、多来源测试与相关文档更新，或执行 `git revert` 回退本次提交
- 若环境中已经创建过 `source_type = nasa_apod` 的任务或内容，回滚前应先确认是否需要保留这些记录，避免后台任务与壁纸数据出现“库里仍有记录、代码已不识别”的状态
- 回滚后仓库将恢复到“仅支持 Bing 采集、`T3.2` 仍停留在设计预留状态”的状态

## 2026-03-26T12:30:40Z

### 变更内容

- 新增 [app/repositories/migrations/versions/V0003__tags.sql](app/repositories/migrations/versions/V0003__tags.sql)，落地 `tags` 与 `wallpaper_tags` 两张标签相关表，并补齐标签状态排序索引和标签反查索引
- 更新 [app/schemas/public.py](app/schemas/public.py)、[app/repositories/public_repository.py](app/repositories/public_repository.py)、[app/services/public_catalog.py](app/services/public_catalog.py) 与 [app/api/public/routes.py](app/api/public/routes.py)，为公开列表新增 `tag_keys` 逗号分隔标签筛选参数，并新增 `/api/public/tags`
- 更新 [app/schemas/admin_content.py](app/schemas/admin_content.py)、[app/repositories/admin_content_repository.py](app/repositories/admin_content_repository.py)、[app/services/admin_content.py](app/services/admin_content.py) 与 [app/api/admin/routes.py](app/api/admin/routes.py)，新增后台标签列表、创建、更新和内容标签绑定接口，并为标签操作补齐审计日志
- 更新 [app/web/routes.py](app/web/routes.py)、[web/admin/assets/admin.js](web/admin/assets/admin.js)、[web/admin/assets/admin.css](web/admin/assets/admin.css)、[web/public/assets/site.js](web/public/assets/site.js) 与 [web/public/assets/site.css](web/public/assets/site.css)，新增 `/admin/tags` 标签管理页、内容详情页标签绑定入口，以及公开列表页标签筛选交互
- 更新 [tests/integration/test_sqlite_migrations.py](tests/integration/test_sqlite_migrations.py)、[tests/integration/test_public_api.py](tests/integration/test_public_api.py)、[tests/integration/test_admin_content.py](tests/integration/test_admin_content.py)、[tests/integration/test_admin_frontend.py](tests/integration/test_admin_frontend.py) 与 [tests/integration/test_public_frontend.py](tests/integration/test_public_frontend.py)，覆盖标签迁移、后台创建更新、标签绑定、公开筛选和前端页面壳
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/data-model.md](docs/data-model.md)，同步 `T3.1` 完成状态、接口契约、当前阶段和后续优先级

### 变更原因

- 完成阶段三 `T3.1`，把“标签定义、后台维护、内容绑定、公开筛选”从预留设计推进为可运行实现
- 保持最保守范围，复用现有 SQLite、FastAPI 和原生前端页面，不提前展开搜索、多来源、OSS/CDN 或新的前端框架
- 让后台标签变更、内容标签绑定与公开筛选共享同一套数据关系，避免后台与公开端对标签口径不一致

### 依赖变更

- 无新增第三方依赖
- 新增数据库迁移：`V0003__tags.sql`
- 变更时间：`2026-03-26T12:30:40Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖标签数据结构、公开列表筛选、公开标签接口、后台标签维护、内容详情页标签绑定和相关审计日志
- 公开列表现在支持 `tag_keys` 逗号分隔参数；当传入多个标签时，当前实现按“同时命中这些标签”处理
- 停用标签不会再出现在公开筛选项中，但后台仍可查看其历史绑定关系
- 不涉及多来源采集、搜索能力、资源派生、OSS/CDN、下载统计、部署方式或运行时版本调整

### 验证步骤

- 执行 `make format`
- 执行 `make verify`

### 回滚说明

- 如需回滚本次变更，可删除标签迁移、回退公开/后台标签接口、页面交互、测试与文档更新，或执行 `git revert` 回退本次提交
- 若目标环境数据库已应用 `V0003__tags.sql`，回滚前应先确认是否需要保留 `tags` / `wallpaper_tags` 现有数据，避免误删已维护的内容标签关系
- 回滚后仓库将恢复到“已完成阶段二闭环，但标签体系仍停留在文档预留状态”的状态

## 2026-03-25T14:24:30Z

### 变更内容

- 新增 [app/services/backup_restore.py](app/services/backup_restore.py)、[scripts/run_backup.py](scripts/run_backup.py) 与 [scripts/run_restore.py](scripts/run_restore.py)，实现 SQLite 一致性备份、正式资源目录/配置目录/日志目录归档，以及 Nginx / `systemd` / `tmpfiles` 配置备份与恢复
- 新增 [scripts/verify_t2_5.py](scripts/verify_t2_5.py) 与 [tests/integration/test_backup_restore.py](tests/integration/test_backup_restore.py)，把“备份 -> 恢复 -> 公开页面/公开 API/后台 API/深度健康检查/资源巡检验证”落成自动化恢复演练
- 更新 [app/schemas/health.py](app/schemas/health.py) 与 [app/services/health.py](app/services/health.py)，让 `/api/health/deep` 返回最近一次恢复验证记录摘要
- 更新 [Makefile](Makefile)，新增 `make backup`、`make restore` 与 `make verify-backup-restore`，并把新的运维脚本纳入 `make typecheck`
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/deployment-runbook.md](docs/deployment-runbook.md)，同步 `T2.5` 完成状态、恢复手册、命令入口、健康检查契约和后续优先级

### 变更原因

- 完成阶段二 `T2.5`，把“备份、恢复、恢复演练、恢复记录可追踪”从设计约束推进为可运行实现
- 继续保持单机保守方案，复用现有 SQLite、本地文件系统、FastAPI 和运维脚本，不引入对象存储、外部备份服务或额外依赖
- 让恢复结果可通过健康检查和自动化演练直接验证，避免只有脚本、没有验收链路

### 依赖变更

- 无新增第三方依赖
- 新增运行入口：`make backup`、`make restore`、`make verify-backup-restore`
- 变更时间：`2026-03-25T14:24:30Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖备份恢复脚本、深度健康检查响应、运维命令入口和相关文档
- 新的备份产物会同时覆盖数据库、正式资源目录、配置目录、日志目录以及 Nginx / `systemd` / `tmpfiles` 部署配置
- 恢复演练成功后，`/api/health/deep` 可返回最近一次恢复验证记录摘要，便于追踪最近一次演练结果
- 不涉及数据库结构变更、公开业务规则变更、后台业务流程变更、目标机 `cron` 真实安装配置或阶段三扩展能力

### 验证步骤

- 执行 `./.venv/bin/python -m ruff check .`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_backup.py scripts/run_restore.py scripts/run_resource_inspection.py scripts/verify_t2_5.py`
- 执行 `make verify`
- 执行 `./.venv/bin/python scripts/verify_t2_5.py`

### 回滚说明

- 如需回滚本次变更，可删除备份恢复 service / 脚本 / 测试，回退 `/api/health/deep` 的恢复验证字段、`make backup` / `make restore` / `make verify-backup-restore` 和相关文档更新，或执行 `git revert` 回退本次提交
- 若环境中已生成新的备份快照、恢复记录或恢复验证记录，回滚前应先确认这些产物是否需要保留归档，避免误删最近一次演练证据
- 回滚后仓库将恢复到“已具备健康检查与资源巡检，但尚未提供备份恢复闭环和恢复演练记录”的状态

## 2026-03-25T13:55:53Z

### 变更内容

- 新增 [app/repositories/health_repository.py](app/repositories/health_repository.py)、[app/services/health.py](app/services/health.py) 与 [app/schemas/health.py](app/schemas/health.py)，落地就绪检查、深度检查、磁盘摘要、最近一次采集任务摘要和资源巡检结果结构
- 更新 [app/api/health.py](app/api/health.py)，新增 `/api/health/ready` 与 `/api/health/deep`，并在数据库、目录或磁盘状态不满足要求时返回明确健康状态和 `503` 响应
- 新增 [scripts/run_resource_inspection.py](scripts/run_resource_inspection.py) 并更新 [Makefile](Makefile)，提供 `make inspect-resources` 巡检入口，同时把新的巡检脚本纳入 `make typecheck` 校验范围
- 新增 [tests/integration/test_health_checks.py](tests/integration/test_health_checks.py)，覆盖就绪检查成功/失败、深度检查摘要，以及资源文件缺失后资源状态失败、内容自动下线和公开接口隔离行为
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/deployment-runbook.md](docs/deployment-runbook.md)，同步 `T2.4` 完成状态、巡检命令、健康检查契约、部署运行说明和下一阶段优先级

### 变更原因

- 完成阶段二 `T2.4`，把健康检查与资源巡检从文档约束推进为可运行实现
- 继续保持最保守方案，复用现有 SQLite、本地文件存储和 FastAPI，不引入任务队列、监控系统或额外依赖
- 让资源丢失时的状态联动进入代码闭环，避免公开端继续暴露已失效的内容

### 依赖变更

- 无新增第三方依赖
- 新增运行入口：`make inspect-resources`
- 调整验证入口：`make typecheck` 现包含 `scripts/run_resource_inspection.py`
- 变更时间：`2026-03-25T13:55:53Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖健康检查 API、资源巡检脚本、资源状态联动、公开可见性隔离、运行命令和相关文档
- 当正式资源文件缺失且该内容已处于公开启用状态时，巡检会把资源标记为失败，并将内容自动降级为 `disabled`
- 不涉及数据库结构变更、备份恢复实现、cron 真实安装配置、阶段三扩展能力或依赖版本升级

### 验证步骤

- 执行 `./.venv/bin/python -m ruff check .`
- 执行 `./.venv/bin/python -m mypy app tests scripts/run_resource_inspection.py`
- 执行 `make verify`

### 回滚说明

- 如需回滚本次变更，可删除健康检查 repository / service / schema、资源巡检脚本与测试，回退 `/api/health/ready`、`/api/health/deep`、`make inspect-resources` 和文档更新，或执行 `git revert` 回退本次提交
- 若环境中已执行过资源巡检，回滚前应先确认是否需要恢复被自动降级为 `disabled` 的内容状态，以及是否要清理 `image_resources.failure_reason` 中新增的巡检失败原因
- 回滚后仓库将恢复到“仅提供 `/api/health/live`、尚未具备资源巡检闭环”的状态

## 2026-03-25T13:39:04Z

### 变更内容

- 新增 [app/schemas/admin_collection.py](app/schemas/admin_collection.py)、[app/repositories/admin_collection_repository.py](app/repositories/admin_collection_repository.py) 与 [app/services/admin_collection.py](app/services/admin_collection.py)，落地手动采集任务创建、任务列表、任务详情、失败任务重试和结构化日志查询的 schema、SQLite 查询逻辑与后台服务
- 更新 [app/api/admin/routes.py](app/api/admin/routes.py)、[app/repositories/collection_repository.py](app/repositories/collection_repository.py) 与 [app/services/bing_collection.py](app/services/bing_collection.py)，接入 `/api/admin/collection-tasks`、`/api/admin/collection-tasks/{task_id}`、`/api/admin/collection-tasks/{task_id}/retry`、`/api/admin/logs`，并把既有 Bing 采集主链路扩展为可消费 `queued` 任务的模式
- 新增 [app/collectors/manual_tasks.py](app/collectors/manual_tasks.py) 并更新 [Makefile](Makefile)，提供 `make consume-collection-tasks` 队列消费入口，便于后续由 cron 直接调用
- 更新 [app/web/routes.py](app/web/routes.py)、[web/admin/assets/admin.js](web/admin/assets/admin.js) 与 [web/admin/assets/admin.css](web/admin/assets/admin.css)，新增 `/admin/tasks`、`/admin/tasks/{task_id}`、`/admin/logs` 后台页面，展示任务创建、执行统计、错误摘要、逐条处理明细和结构化日志
- 新增 [tests/integration/test_admin_collection.py](tests/integration/test_admin_collection.py)，并更新 [tests/integration/test_admin_frontend.py](tests/integration/test_admin_frontend.py)，覆盖任务创建、队列消费、失败日志查询、任务重试和后台任务页面壳
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md)、[docs/api-conventions.md](docs/api-conventions.md) 与 [docs/deployment-runbook.md](docs/deployment-runbook.md)，同步 `T2.3` 完成状态、运行命令、接口约定和后续优先级

### 变更原因

- 完成阶段二 `T2.3`，把“后台提交任务、cron 近实时消费、后台查看结果和失败原因”的设计约束推进为可运行实现
- 继续保持最保守方案，复用既有 Bing 采集主链路和后台页面技术栈，不引入消息队列、新前端框架或额外部署组件
- 让手动采集与自动采集继续共用同一条采集逻辑，同时把任务状态、结构化日志和失败定位统一落到数据库中

### 依赖变更

- 无新增第三方依赖
- 新增运行入口：`make consume-collection-tasks`
- 变更时间：`2026-03-25T13:39:04Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖后台任务 API、后台任务页面、结构化日志查询、手动采集任务队列消费、任务重试与审计日志写入
- 当前实现仅支持 `source_type = bing`，并对 Bing 手动采集日期范围采用最近 `8` 天的保守窗口约束
- 不涉及 `/api/health/ready`、`/api/health/deep`、备份恢复、阶段三扩展能力或依赖版本升级

### 验证步骤

- 执行 `./.venv/bin/python -m ruff check app tests web`
- 执行 `./.venv/bin/python -m mypy app tests`
- 执行 `./.venv/bin/python -m pytest`

### 回滚说明

- 如需回滚本次变更，可删除后台任务相关 schema / repository / service / 页面 / 测试，回退新的后台 API 路由、队列消费入口与文档更新，或执行 `git revert` 回退本次提交
- 若目标环境已经开始使用 `/api/admin/collection-tasks` 创建新任务，回滚前应先确认是否需要保留 `collection_tasks`、`collection_task_items` 和 `audit_logs` 中新增的后台任务记录
- 回滚后仓库将恢复到“已具备后台内容管理与审计查询，但尚未提供手动采集任务与后台观测闭环”的状态

## 2026-03-25T13:12:07Z

### 变更内容

- 新增 [app/schemas/admin_content.py](app/schemas/admin_content.py)、[app/repositories/admin_content_repository.py](app/repositories/admin_content_repository.py) 与 [app/services/admin_content.py](app/services/admin_content.py)，落地后台内容列表、详情、状态切换和审计查询的 schema、SQLite 查询逻辑与状态流转服务
- 更新 [app/api/admin/routes.py](app/api/admin/routes.py)，接入 `/api/admin/wallpapers`、`/api/admin/wallpapers/{wallpaper_id}`、`/api/admin/wallpapers/{wallpaper_id}/status` 与 `/api/admin/audit-logs`，并复用既有后台会话鉴权能力
- 更新 [app/web/routes.py](app/web/routes.py)、[app/web/__init__.py](app/web/__init__.py) 与 [app/main.py](app/main.py)，新增 `/admin/login`、`/admin`、`/admin/wallpapers/{wallpaper_id}`、`/admin/audit-logs` 后台页面，以及 `/admin-assets/*` 后台静态资源挂载
- 新增 [web/admin/assets/admin.js](web/admin/assets/admin.js) 与 [web/admin/assets/admin.css](web/admin/assets/admin.css)，实现后台登录页、内容管理页、内容详情页和审计记录页的最小前端，并约束页面仅通过后台 API 工作
- 新增 [tests/integration/test_admin_content.py](tests/integration/test_admin_content.py) 与 [tests/integration/test_admin_frontend.py](tests/integration/test_admin_frontend.py)，并更新 [tests/integration/test_public_api.py](tests/integration/test_public_api.py)，覆盖状态切换、非法流转拦截、审计查询、后台页面壳和公开可见性联动
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md) 与 [docs/api-conventions.md](docs/api-conventions.md)，同步 `T2.2` 完成状态、后台接口契约、验证方式和下一阶段优先级

### 变更原因

- 完成阶段二 `T2.2`，把后台内容管理、状态切换和审计查询从设计文档推进为可运行实现
- 保持保守范围，继续沿用 FastAPI 托管页面骨架与原生 HTML/CSS/JavaScript，不提前展开手动采集任务页、日志页或新前端框架引入
- 保证后台页面全部经由后台 API 工作，同时让状态切换结果能与公开接口可见性形成可验证联动

### 依赖变更

- 无新增第三方依赖
- 继续使用现有 FastAPI、Pydantic、SQLite 与原生前端资源组织方式
- 变更时间：`2026-03-25T13:12:07Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖后台内容管理 API、后台页面、审计查询、内容状态流转、审计日志写入和相关集成测试
- 被禁用或逻辑删除的内容将不再通过公开接口返回；后台详情页会展示失败原因和最近操作记录
- 不涉及采集主链路、任务消费 cron、健康检查、备份恢复、部署模板或依赖版本升级

### 验证步骤

- 执行 `./.venv/bin/python -m ruff check .`
- 执行 `./.venv/bin/python -m mypy app tests`
- 执行 `./.venv/bin/python -m pytest`

### 回滚说明

- 如需回滚本次变更，可删除后台内容管理服务、后台页面与测试，回退相关 API 路由和文档更新，或执行 `git revert` 回退本次提交
- 若环境中已有管理员执行过内容状态切换，回滚代码前应先确认当前内容状态是否需要手工恢复，以避免公开端与运营预期不一致
- 回滚后仓库将恢复到“具备后台登录与会话控制，但尚未提供后台内容管理与审计查询页面”的状态

## 2026-03-25T12:49:06Z

### 变更内容

- 新增 [app/repositories/migrations/versions/V0002__admin_sessions.sql](app/repositories/migrations/versions/V0002__admin_sessions.sql)，把后台会话表 `admin_sessions` 以独立迁移方式落地，并补齐 `(session_token_hash)` 唯一索引与 `(admin_user_id, expires_at_utc)` 会话校验索引
- 新增 [app/core/security.py](app/core/security.py)、[app/repositories/admin_auth_repository.py](app/repositories/admin_auth_repository.py)、[app/services/admin_auth.py](app/services/admin_auth.py)、[app/schemas/admin_auth.py](app/schemas/admin_auth.py) 与 [app/api/admin/routes.py](app/api/admin/routes.py)，落地管理员密码摘要校验、会话令牌签发与摘要存储、会话过期判断、主动登出失效、审计日志写入和当前管理员上下文注入
- 更新 [app/api/router.py](app/api/router.py) 与 [app/api/admin/__init__.py](app/api/admin/__init__.py)，接入 `/api/admin/auth/login`、`/api/admin/auth/logout` 两个后台认证接口
- 新增 [tests/integration/test_admin_auth.py](tests/integration/test_admin_auth.py) 与 [tests/unit/test_security.py](tests/unit/test_security.py)，覆盖正确登录、错误登录、禁用账号、会话过期、登出失效、密码摘要与会话摘要关键路径
- 更新 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/TODO.md](docs/TODO.md) 与 [docs/api-conventions.md](docs/api-conventions.md)，同步 `T2.1` 完成状态、后台鉴权使用方式和后续优先级

### 变更原因

- 完成阶段二 `T2.1`，把后台登录、登出、会话控制和基础鉴权能力从设计文档推进为可运行实现
- 保持保守范围，只补齐后台认证入口和会话基础设施，不提前展开后台内容管理页面、任务管理或额外框架引入
- 为 `T2.2` 后台内容管理接口与页面提供统一的管理员上下文、错误码和审计基础

### 依赖变更

- 无新增第三方依赖
- 密码摘要、会话令牌哈希和客户端摘要基于 Python 标准库 `hashlib`、`hmac`、`secrets` 实现
- 变更时间：`2026-03-25T12:49:06Z`
- 依赖类型：无直接或间接第三方包变更

### 影响范围

- 影响范围覆盖后台认证 API、管理员会话持久化、审计日志写入、后台鉴权测试和相关文档同步
- 公开 API、公开前端、采集链路、部署模板和现有依赖版本均未改动
- 新会话默认通过 `Authorization: Bearer <session_token>` 使用，服务端仅保存会话令牌摘要，不保存明文令牌

### 验证步骤

- 执行 `make format`
- 执行 `make lint`
- 执行 `make typecheck`
- 执行 `make test`

### 回滚说明

- 如需回滚本次变更，可删除后台鉴权代码与测试、回退 [app/repositories/migrations/versions/V0002__admin_sessions.sql](app/repositories/migrations/versions/V0002__admin_sessions.sql) 以及相关文档更新，或执行 `git revert` 回退本次提交
- 若目标环境数据库已应用 `V0002__admin_sessions.sql`，回滚前应先停用后台登录调用，并删除 `admin_sessions` 表及其索引后再回退代码
- 回滚后仓库将恢复到“已具备阶段一公开链路，但尚未提供后台登录与会话控制”的状态

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
