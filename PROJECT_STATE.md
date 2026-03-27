# PROJECT_STATE

## 文档元信息

- 更新时间：2026-03-27T16:02:25Z
- 当前阶段：阶段三功能已完成，运维侧仍需补齐目标机 `cron` 安装与计划配置
- 状态说明：仓库已完成一期系统设计总纲、配套文档骨架、经系统级校准的阶段路线图，并已落地 `T1.1` 的最小后端工程骨架、`T1.2` 的 SQLite 迁移基线、`T1.3` 的 Bing 采集、去重、任务记录、图片下载与资源入库主链路、`T1.4` 的公开 API 最小集、`T1.5` 的基础公开前端、`T1.6` 的单机部署模板与自动化部署验收，以及 `T2.1` 的管理员认证与会话控制、`T2.2` 的后台内容管理 API / 页面与审计查询、`T2.3` 的手动采集任务与后台观测、`T2.4` 的健康检查与资源巡检闭环、`T2.5` 的备份恢复与恢复演练闭环、`T3.1` 的标签体系、`T3.2` 的多来源采集、`T3.3` 的资源派生版本、`T3.4` 的 OSS / CDN 兼容资源定位、`T3.5` 的下载登记与后台统计、`T3.6` 的关键词搜索增强

## 项目目的

BingWall 的目标是构建一个围绕 Bing 壁纸的图片服务系统，在单机架构下完成以下闭环：

- 自动与手动采集壁纸及元数据
- 保存内容数据和图片资源
- 对外提供公开 API
- 提供公开浏览与下载页面
- 提供后台管理能力
- 为后续多来源、标签、搜索、OSS 和统计能力预留扩展空间

## 当前技术路线

以下为当前阶段已经采用的技术路线：

- 部署形态：单机部署
- 操作系统：Ubuntu
- 后端：Python `3.14.2` + FastAPI + Pillow `12.1.1`
- 前端与构建运行时：Node.js `24.13.0`
- 数据库：SQLite
- 定时任务：cron
- Web 服务：Nginx
- 进程托管：systemd
- 文件存储：本地目录，兼容 OSS / CDN 资源定位

## 运行说明

当前仓库已经包含最小可执行后端实现，因此：

- 已提供 `make setup`、`make db-migrate`、`make collect-bing`、`make collect-nasa-apod`、`make consume-collection-tasks`、`make inspect-resources`、`make backup`、`make restore`、`make verify`、`make verify-deploy`、`make verify-backup-restore`、`make run` 统一命令入口
- `make run` 现已改为跟随 `.env` / 环境变量中的 `BINGWALL_APP_HOST` 与 `BINGWALL_APP_PORT`，避免启动端口与配置声明不一致
- 已提供 `/api/health/live`、`/api/health/ready`、`/api/health/deep` 健康检查接口
- 已提供 `/api/public/wallpapers`、`/api/public/wallpapers/today`、`/api/public/wallpapers/random`、`/api/public/wallpaper-filters`、`/api/public/tags`、`/api/public/site-info`、`/api/public/wallpapers/{wallpaper_id}` 和 `/api/public/download-events` 公开接口，其中列表默认返回缩略图资源，并支持 `keyword`、`tag_keys`、`date_from`、`date_to`、地区和分辨率组合查询；日期格式固定为 `YYYY-MM-DD`，并按 `wallpaper_date` 做包含边界的范围过滤；详情区分预览图与下载图，`today` 按 UTC 当天匹配并优先默认市场，`random` 仅从当前公开可见内容中随机返回，下载登记接口负责记录行为并返回静态资源地址
- 已提供 `/api/admin/auth/login`、`/api/admin/auth/logout`、`/api/admin/wallpapers`、`/api/admin/wallpapers/{wallpaper_id}`、`/api/admin/wallpapers/{wallpaper_id}/status`、`/api/admin/wallpapers/{wallpaper_id}/tags`、`/api/admin/tags`、`/api/admin/tags/{tag_id}`、`/api/admin/collection-tasks`、`/api/admin/collection-tasks/{task_id}`、`/api/admin/collection-tasks/{task_id}/consume`、`/api/admin/collection-tasks/{task_id}/retry`、`/api/admin/logs`、`/api/admin/audit-logs` 和 `/api/admin/download-stats` 后台接口，其中内容列表已支持 `keyword + 状态` 联合检索
- 已提供 `/`、`/wallpapers`、`/wallpapers/{wallpaper_id}` 公开页面，以及 `/admin/login`、`/admin`、`/admin/wallpapers/{wallpaper_id}`、`/admin/tags`、`/admin/tasks`、`/admin/tasks/{task_id}`、`/admin/download-stats`、`/admin/logs`、`/admin/audit-logs` 后台页面；公开列表页与后台内容页均已增加关键词搜索输入
- 已提供 `/assets/*` 公开静态资源、`/admin-assets/*` 后台静态资源和 `/images/*` 本地开发图片访问挂载；当资源记录使用 `storage_backend = oss` 时，公开接口会直接返回配置的 OSS / CDN 公网地址
- 已提供 SQLite 数据库初始化命令
- 已提供 `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 和 `deploy/systemd/bingwall.env.example` 单机部署模板
- 已提供 `scripts/verify_t1_6.py`，可在不改写系统级服务配置的前提下执行 `T1.6` 自动化部署验收
- 已提供 `scripts/run_resource_inspection.py`，可执行本地资源巡检并在发现资源缺失时自动刷新资源与内容状态
- 已提供 `scripts/run_backup.py`、`scripts/run_restore.py` 与 `scripts/verify_t2_5.py`，可执行备份、恢复和恢复演练
- 已生成运行时版本锁定文件和 Python 依赖锁定文件

后续要求：

- 后续仍需补齐目标机 cron 安装配置

## 目录职责

- `README.md`：项目总入口和文档导航
- `PROJECT_STATE.md`：项目状态、当前阶段、关键决策和待办摘要
- `CHANGELOG.md`：面向交付和协作的变更记录
- `docs/system-design.md`：系统设计总纲
- `docs/README.md`：文档体系索引
- `docs/module-overview.md`：模块边界、职责和建议目录
- `docs/data-model.md`：数据实体、状态模型、约束和索引建议
- `docs/api-conventions.md`：接口边界、统一响应、核心接口契约
- `docs/deployment-runbook.md`：部署、配置、运行、备份、恢复和健康检查要求
- `docs/TODO.md`：按阶段拆解的 TODO、依赖和验收标准

## 已完成内容

- 已形成一期系统设计总纲
- 已补齐实施前需要的核心配套文档
- 已将开发工作拆分为阶段一、阶段二、阶段三 TODO
- 已完成 `docs/TODO.md` 的系统级校准，补齐来源标注、依赖拓扑和验收口径
- 已修正文档间的公开规则冲突，并补齐后台详情、日志和审计相关接口契约
- 已补齐管理员会话、标签、下载登记等阶段二/三预留数据结构
- 已修正运维依赖链、资源状态同步机制、登出接口和配置基线说明
- 已建立与 `docs/module-overview.md` 一致的后端目录骨架
- 已新增 `.python-version`、`.nvmrc`、`pyproject.toml`、`requirements.lock.txt` 和 `.env.example`
- 已实现统一配置加载入口，覆盖服务监听、数据库路径、存储目录和安全配置的必填校验
- 已实现最小 FastAPI 服务、根路由和 `/api/health/live` 健康检查
- 已补齐 `make setup`、`make verify`、`make run` 命令入口，以及 `pytest`、`ruff`、`mypy` 基础校验
- 已实现 SQLite 版本化迁移基线，并新增 `schema_migrations` 管理表
- 已通过迁移脚本落地 `wallpapers`、`image_resources`、`collection_tasks`、`collection_task_items`、`admin_users`、`audit_logs` 六张核心表
- 已落地 `source_type + wallpaper_date + market_code` 唯一约束，以及公开查询、任务查询和状态筛选所需关键索引
- 已补齐空库初始化与重复执行迁移能力，并增加迁移结构校验测试
- 已实现 Bing 元数据拉取、字段映射、业务主键与 `source_url_hash` 双层去重判断
- 已实现采集任务汇总、逐条明细记录、下载重试和失败原因落库
- 已实现图片先入临时目录、校验通过后转正式资源目录、失败转隔离目录的资源入库链路
- 已实现 `image_status` 与 `resource_status` 联动刷新，并补齐成功、重复、失败、重试耗尽四类集成测试
- 已实现公开列表、详情、筛选项和站点信息四个公开 API 接口
- 已实现统一公开成功响应、统一错误响应、分页结构和公开查询参数校验
- 已实现公开可见规则过滤，只返回 `content_status = enabled`、`is_public = true`、资源状态就绪且处于发布时间窗口内的数据
- 已实现请求 `trace_id` 回传和访问日志记录，并补齐公开 API 集成测试
- 已实现首页、列表页、详情页三个公开页面，并由原生 HTML、CSS、JavaScript 组成基础前端
- 已实现列表筛选、分页刷新、详情下载按钮显隐和空结果/不存在/服务繁忙提示
- 已实现页面静态资源挂载和本地开发图片访问挂载，并补齐公开前端集成测试
- 已新增 `deploy/nginx/bingwall.conf`，区分公开页面、公开 API、页面静态资源和正式图片资源访问路径
- 已新增 `deploy/systemd/bingwall-api.service`，使用受控环境文件启动 FastAPI，并提供失败重启参数
- 已新增 `deploy/systemd/bingwall.tmpfiles.conf`，约定数据库、图片、日志、备份和配置目录的权限
- 已新增 `deploy/systemd/bingwall.env.example`，为生产环境提供独立配置示例
- 已补齐 `README.md` 中的单机部署步骤、数据库初始化命令、systemd 与 Nginx 安装步骤，以及最小上线检查方法
- 已补齐部署模板测试，约束 Nginx 路由、systemd 环境文件和目录权限模板的关键内容
- 已新增 `scripts/verify_t1_6.py` 与 `make verify-deploy`，统一执行 `systemd` 单元离线校验、`tmpfiles` 模板校验、临时 `systemd --user` 服务重启验证和 Docker 化 `nginx` 代理验证
- 已在当前仓库环境完成 `T1.6` 自动化验收，确认公开页面、公开 API、图片静态资源、应用日志和代理日志链路均可工作
- 已新增 `V0002__admin_sessions.sql`，把 `admin_sessions` 作为独立迁移落地，并补齐会话唯一索引和会话校验索引
- 已新增后台密码摘要与会话摘要工具，采用标准库实现密码校验、会话令牌签发和客户端信息摘要
- 已实现 `/api/admin/auth/login` 与 `/api/admin/auth/logout`，支持数据库持久化会话、过期判断、主动失效和统一错误响应
- 已实现后台鉴权依赖，可向后续后台接口注入当前管理员上下文
- 已补齐登录/登出审计日志写入，以及后台鉴权的单元测试与集成测试
- 已新增 `app/schemas/admin_content.py`、`app/repositories/admin_content_repository.py` 与 `app/services/admin_content.py`，实现后台内容列表、详情、状态切换和审计查询所需 schema、查询与状态流转服务
- 已实现 `/api/admin/wallpapers`、`/api/admin/wallpapers/{wallpaper_id}`、`/api/admin/wallpapers/{wallpaper_id}/status` 与 `/api/admin/audit-logs`，支持后台按状态 / 地区 / 时间筛选内容、查看详情、执行启用 / 禁用 / 逻辑删除，并按对象或时间范围查询审计记录
- 已实现 `/admin/login`、`/admin`、`/admin/wallpapers/{wallpaper_id}` 与 `/admin/audit-logs` 后台页面，并通过 `web/admin/assets/admin.js`、`web/admin/assets/admin.css` 约束页面仅调用后台 API，不直接访问数据库或图片目录
- 已补齐后台内容管理与后台页面集成测试，覆盖状态切换、非法流转拦截、审计查询和公开接口联动隐藏行为
- 已新增 `app/schemas/admin_collection.py`、`app/repositories/admin_collection_repository.py` 与 `app/services/admin_collection.py`，实现手动采集任务创建、任务列表、任务详情、`queued` 任务人工触发、失败任务重试和结构化日志查询所需 schema、SQLite 查询逻辑与后台服务
- 已扩展 `app/services/bing_collection.py` 与 `app/repositories/collection_repository.py`，支持既有 Bing 采集链路消费 `queued` 任务、按日期范围过滤 Bing 返回数据，并以 `queued -> running -> succeeded / partially_failed / failed` 方式落库任务状态
- 已新增 `/api/admin/collection-tasks`、`/api/admin/collection-tasks/{task_id}`、`/api/admin/collection-tasks/{task_id}/consume`、`/api/admin/collection-tasks/{task_id}/retry` 与 `/api/admin/logs`，并补齐手动采集任务创建、人工触发与重试审计日志
- 已新增 `/admin/tasks`、`/admin/tasks/{task_id}`、`/admin/logs` 后台页面，支持手动提交采集任务、手动触发 queued 任务、查看成功数 / 重复数 / 失败数、错误摘要和逐条处理明细
- 已新增 `app/collectors/manual_tasks.py` 与 `make consume-collection-tasks`，为 cron 提供可直接调用的队列消费入口，同时保留后台按任务手动触发单次执行能力
- 已补齐手动采集任务与后台观测集成测试，覆盖任务创建、任务消费、人工触发、失败日志查询、任务重试和后台页面壳
- 已新增 `app/repositories/health_repository.py`、`app/services/health.py` 与 `app/schemas/health.py`，实现数据库可用性检查、目录可访问性检查、磁盘摘要、最近一次采集任务摘要和资源目录摘要
- 已实现 `/api/health/ready` 与 `/api/health/deep`，支持在就绪失败时返回 `503`，并在深度检查中返回最近任务状态与磁盘使用概览
- 已新增 `scripts/run_resource_inspection.py` 与 `make inspect-resources`，支持巡检正式资源目录并在文件丢失时把资源标记为 `failed`
- 已实现资源巡检异常后的状态联动：当公开启用内容的正式资源丢失时，自动刷新 `resource_status` 并将内容降级为 `disabled`，使公开接口不再返回该内容
- 已补齐健康检查与资源巡检集成测试，覆盖 `ready` 成功/失败、`deep` 摘要返回和资源丢失后的公开链路隔离
- 已新增 `app/services/backup_restore.py`、`scripts/run_backup.py` 与 `scripts/run_restore.py`，实现 SQLite 一致性备份、正式资源目录/配置目录/日志目录归档，以及 Nginx / systemd / tmpfiles 配置备份与恢复
- 已新增 `scripts/verify_t2_5.py` 与 `tests/integration/test_backup_restore.py`，把“备份 -> 恢复 -> 页面/API/深度健康检查/资源巡检验证”落成自动化恢复演练
- 已扩展 `/api/health/deep`，支持返回最近一次恢复验证记录摘要，便于追踪恢复演练结果
- 已新增 `V0003__tags.sql`，把 `tags` 与 `wallpaper_tags` 作为独立迁移落地，并补齐标签状态排序索引和标签反查索引
- 已扩展公开 API：`/api/public/wallpapers` 新增 `tag_keys` 逗号分隔标签筛选参数，`/api/public/wallpaper-filters` 新增标签输出，`/api/public/tags` 返回可公开使用的启用标签
- 已扩展后台内容管理：`/api/admin/tags`、`/api/admin/tags/{tag_id}` 与 `/api/admin/wallpapers/{wallpaper_id}/tags` 支持标签列表、创建、更新和内容标签绑定，并写入审计日志
- 已新增 `/admin/tags` 标签管理页，并在 `/admin/wallpapers/{wallpaper_id}` 内容详情页增加标签绑定区，确保后台仍只通过后台 API 管理标签
- 已补齐标签体系集成测试，覆盖标签迁移、后台创建更新、内容标签绑定、公开标签筛选和停用标签隐藏联动
- 已新增 `app/services/source_collection.py` 与 `app/domain/collection_sources.py`，把采集主链路抽象为按 `source_type` 分发的统一来源接口，同时保留 Bing 现有服务外观不变
- 已新增 `app/collectors/nasa_apod.py`、`make collect-nasa-apod` 与 `BINGWALL_COLLECT_NASA_APOD_*` 配置，接入 `nasa_apod` 作为 Bing 之外的新来源，并采用 `market_code = global` 的保守口径
- 已扩展后台任务创建与消费链路：`/api/admin/collection-tasks`、重试逻辑、任务认领逻辑、后台任务页面来源下拉和结构化日志均可区分 `bing` / `nasa_apod`
- 已补齐多来源采集集成测试，覆盖 Bing 稳定性不回归、NASA APOD 新来源入库、后台任务消费和来源日志可观测性
- 已新增 `app/services/image_variants.py`、`app/domain/resource_variants.py` 与迁移 `V0004__image_resource_variants.sql`，把 `image_resources.resource_type` 规范扩展为 `original` / `thumbnail` / `preview` / `download`
- 已扩展采集主链路：原图入库成功后会生成缩略图、详情预览图和下载图，并把失败原因同步写入资源状态与任务日志
- 已调整公开资源选择策略：列表默认返回 `thumbnail_url`，详情返回 `preview_url` 与 `download_url`，不再让列表页直接依赖原图
- 已补齐资源派生版本测试，覆盖多版本资源入库、列表/详情资源选择、派生失败日志可观测性和迁移重复执行校验
- 已新增 `app/services/resource_locator.py` 与 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 配置，把资源定位从硬编码 `/images/<relative_path>` 抽象为可同时支持 `local` / `oss` 的统一入口
- 已扩展公开接口与后台内容接口：当资源记录的 `storage_backend = local` 时继续返回 `/images/<relative_path>`，当 `storage_backend = oss` 时返回配置好的 OSS / CDN 公网地址，并保留历史本地资源访问兼容
- 已补齐 OSS / 本地并存测试、资源定位单元测试和配置加载测试，验证公开列表、公开详情、后台列表和后台详情在迁移期间不会暴露服务器磁盘路径
- 已新增 `V0005__download_events.sql`、`app/repositories/download_repository.py` 与 `app/services/downloads.py`，把下载登记、公开下载目标解析、降级日志和后台统计聚合落成可运行实现
- 已实现 `/api/public/download-events`，支持公开详情页在真实静态资源下载前先登记 `wallpaper_id`、入口来源、请求追踪 ID、IP/UA 摘要与跳转地址；当登记失败时写入降级日志但继续返回静态资源地址
- 已实现 `/api/admin/download-stats` 与 `/admin/download-stats`，支持后台查看最近 7 / 30 / 90 天下载总量、成功跳转数、拦截数、登记降级数、热门内容和按日趋势
- 已补齐下载登记与下载统计集成测试、迁移校验和前后台页面壳校验，确认文件传输主流量仍由 `/images/*` 或 OSS / CDN 静态链路承担
- 已扩展公开列表与后台内容列表查询参数，新增 `keyword` 并统一匹配标题、简述、版权说明、描述和标签来源；公开端仅匹配启用标签，后台端保留全部已绑定标签匹配能力
- 已扩展公开列表查询参数，新增 `date_from` 与 `date_to` 两个日期范围筛选参数，支持按 `wallpaper_date` 做 `YYYY-MM-DD` 闭区间过滤，并与既有关键词、标签、地区、分辨率和分页条件组合使用
- 已新增 `V0006__admin_user_status_constraint.sql`，把 `admin_users.status` 在数据库层收敛为 `enabled` / `disabled` 两个枚举值；迁移会先把 legacy 的 `active` 归一化为 `enabled`，并将其他未知非法值保守降级为 `disabled`
- 已为采集链路新增 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED` 开关，当前默认开启；新采集内容会在资源全部就绪后自动切到 `enabled` 且 `is_public = true`，若关闭该开关则继续保持 `draft`
- 已更新 `/wallpapers` 与 `/admin/wallpapers` 前端交互，支持关键词与既有筛选条件组合查询，且页面仍只通过既有公开 / 后台 API 读取业务数据
- 已补齐关键词搜索集成测试，验证公开与后台结果差异可由状态规则解释，并记录 30 条代表性样本下公开搜索约 `0.0043` 秒、后台搜索约 `0.0058` 秒，满足 `1` 秒内返回目标
- 已补充服务器实测部署排障结论：`BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 在仅本地文件存储场景应保持未设置，若写成空字符串会触发配置校验失败；当资源使用 `storage_backend = oss` 时则必须配置真实公网地址
- 已支持通过 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD` 在数据库初始化时自动创建首个启用中的 `super_admin`，且仅在 `admin_users` 为空时生效
- 已新增 `/api/public/wallpapers/today` 与 `/api/public/wallpapers/random`，两者都返回与公开详情一致的单条壁纸结构；其中 `today` 按 UTC 日期匹配当天公开内容并优先站点默认市场，`random` 仅从当前公开可见内容中随机选取
- 已修正 SQLite 连接在 FastAPI 同步依赖与同步路由分属不同工作线程时触发的线程限制问题，避免公开列表、筛选项等接口偶发返回 `500 Internal Server Error`

## 未完成内容

- 尚未完成目标机 cron 安装配置
- 尚未落地真实目标机的长期驻留部署与公网域名接入，这属于后续运维执行动作，不再阻塞 `T1.6`

## 当前开放问题

- 下载统计当前只覆盖下载登记、热门内容和最近 90 天按日趋势，是否继续扩展到地区偏好、来源对比和更细粒度指标仍需确认
- 告警渠道采用邮件、Webhook 还是其他方式，仍需在运维实施前确认
- 当前关键词搜索采用 SQLite `LIKE` 保守实现；若后续数据量显著增长，再评估是否引入专门索引或全文检索方案

## 关键设计决策

- 一期以单机架构落地，不做微服务拆分
- 一期以 SQLite 作为结构化数据存储
- 一期以本地文件系统存储图片资源
- 一期以 cron 负责定时调度，避免过早引入消息队列
- 一期公开前端采用“FastAPI 托管页面骨架 + 原生 HTML/CSS/JavaScript + 只读公开 API”的保守方案
- 一期后台继续采用“FastAPI 托管页面骨架 + 原生 HTML/CSS/JavaScript + 后台 API 驱动”的保守方案
- 内容状态与图片状态必须联动，公开接口只能返回 `enabled`、允许公开展示、资源可用且处于发布时间窗口内的数据
- 手动采集采用“后台提交任务，默认仍由 cron 近实时消费，同时允许管理员对单个 queued 任务手动触发一次执行”的保守方案
- 一期后台会话采用数据库持久化模式，服务端只保存会话令牌摘要
- 标签体系采用“后台定义标签 + 内容详情页绑定 + 公开端按 `tag_keys` 逗号分隔参数做多标签同时命中筛选”的保守方案
- 多来源采集采用“统一采集服务 + 来源适配器 + `source_type` 分发”的保守方案，当前新增来源为 `nasa_apod`，其 `market_code` 固定为 `global`
- 自动发布策略当前采用“默认开启自动公开 + 配置可关闭回到人工审核”的保守方案，避免每次采集后手工改库，同时保留回退路径
- OSS/CDN 适配采用“只先抽象资源定位与地址生成，不提前引入对象存储 SDK、不改现有本地写入链路”的保守方案
- 下载统计采用“公开下载登记接口 + 静态资源直链 + 后台聚合视图”的保守方案，不让应用服务承担大文件主传输
- 搜索能力采用“在现有公开 / 后台列表接口上增加 `keyword` 参数 + SQLite `LIKE` 匹配既有文本字段和标签”的保守方案，不引入全文检索引擎或新索引表

## 后续优先级

1. 先补齐目标机 cron 安装与计划配置
2. 再推进真实目标机长期驻留部署与公网域名接入
