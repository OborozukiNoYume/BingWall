# PROJECT_STATE

## 文档元信息

- 更新时间：2026-03-25T13:55:53Z
- 当前阶段：阶段二进行中，`T2.4` 已完成，下一优先级为 `T2.5`
- 状态说明：仓库已完成一期系统设计总纲、配套文档骨架、经系统级校准的阶段路线图，并已落地 `T1.1` 的最小后端工程骨架、`T1.2` 的 SQLite 迁移基线、`T1.3` 的 Bing 采集、去重、任务记录、图片下载与资源入库主链路、`T1.4` 的公开 API 最小集、`T1.5` 的基础公开前端、`T1.6` 的单机部署模板与自动化部署验收，以及 `T2.1` 的管理员认证与会话控制、`T2.2` 的后台内容管理 API / 页面与审计查询、`T2.3` 的手动采集任务与后台观测、`T2.4` 的健康检查与资源巡检闭环

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
- 后端：Python `3.14.2` + FastAPI
- 前端与构建运行时：Node.js `24.13.0`
- 数据库：SQLite
- 定时任务：cron
- Web 服务：Nginx
- 进程托管：systemd
- 文件存储：本地目录

## 运行说明

当前仓库已经包含最小可执行后端实现，因此：

- 已提供 `make setup`、`make db-migrate`、`make collect-bing`、`make consume-collection-tasks`、`make inspect-resources`、`make verify`、`make verify-deploy`、`make run` 统一命令入口
- 已提供 `/api/health/live`、`/api/health/ready`、`/api/health/deep` 健康检查接口
- 已提供 `/api/public/wallpapers`、`/api/public/wallpaper-filters`、`/api/public/site-info` 和 `/api/public/wallpapers/{wallpaper_id}` 公开接口
- 已提供 `/api/admin/auth/login`、`/api/admin/auth/logout`、`/api/admin/wallpapers`、`/api/admin/wallpapers/{wallpaper_id}`、`/api/admin/wallpapers/{wallpaper_id}/status`、`/api/admin/collection-tasks`、`/api/admin/collection-tasks/{task_id}`、`/api/admin/collection-tasks/{task_id}/retry`、`/api/admin/logs` 和 `/api/admin/audit-logs` 后台接口
- 已提供 `/`、`/wallpapers`、`/wallpapers/{wallpaper_id}` 公开页面，以及 `/admin/login`、`/admin`、`/admin/wallpapers/{wallpaper_id}`、`/admin/tasks`、`/admin/tasks/{task_id}`、`/admin/logs`、`/admin/audit-logs` 后台页面
- 已提供 `/assets/*` 公开静态资源、`/admin-assets/*` 后台静态资源和 `/images/*` 本地开发图片访问挂载
- 已提供 SQLite 数据库初始化命令
- 已提供 `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 和 `deploy/systemd/bingwall.env.example` 单机部署模板
- 已提供 `scripts/verify_t1_6.py`，可在不改写系统级服务配置的前提下执行 `T1.6` 自动化部署验收
- 已提供 `scripts/run_resource_inspection.py`，可执行本地资源巡检并在发现资源缺失时自动刷新资源与内容状态
- 已生成运行时版本锁定文件和 Python 依赖锁定文件

后续要求：

- 后续仍需补齐备份恢复与目标机 cron 安装配置

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
- 已新增 `app/schemas/admin_collection.py`、`app/repositories/admin_collection_repository.py` 与 `app/services/admin_collection.py`，实现手动采集任务创建、任务列表、任务详情、失败任务重试和结构化日志查询所需 schema、SQLite 查询逻辑与后台服务
- 已扩展 `app/services/bing_collection.py` 与 `app/repositories/collection_repository.py`，支持既有 Bing 采集链路消费 `queued` 任务、按日期范围过滤 Bing 返回数据，并以 `queued -> running -> succeeded / partially_failed / failed` 方式落库任务状态
- 已新增 `/api/admin/collection-tasks`、`/api/admin/collection-tasks/{task_id}`、`/api/admin/collection-tasks/{task_id}/retry` 与 `/api/admin/logs`，并补齐手动采集任务创建与重试审计日志
- 已新增 `/admin/tasks`、`/admin/tasks/{task_id}`、`/admin/logs` 后台页面，支持手动提交采集任务、查看成功数 / 重复数 / 失败数、错误摘要和逐条处理明细
- 已新增 `app/collectors/manual_tasks.py` 与 `make consume-collection-tasks`，为 cron 提供可直接调用的手动采集任务消费入口
- 已补齐手动采集任务与后台观测集成测试，覆盖任务创建、任务消费、失败日志查询、任务重试和后台页面壳
- 已新增 `app/repositories/health_repository.py`、`app/services/health.py` 与 `app/schemas/health.py`，实现数据库可用性检查、目录可访问性检查、磁盘摘要、最近一次采集任务摘要和资源目录摘要
- 已实现 `/api/health/ready` 与 `/api/health/deep`，支持在就绪失败时返回 `503`，并在深度检查中返回最近任务状态与磁盘使用概览
- 已新增 `scripts/run_resource_inspection.py` 与 `make inspect-resources`，支持巡检正式资源目录并在文件丢失时把资源标记为 `failed`
- 已实现资源巡检异常后的状态联动：当公开启用内容的正式资源丢失时，自动刷新 `resource_status` 并将内容降级为 `disabled`，使公开接口不再返回该内容
- 已补齐健康检查与资源巡检集成测试，覆盖 `ready` 成功/失败、`deep` 摘要返回和资源丢失后的公开链路隔离

## 未完成内容

- 尚未实现备份恢复，以及目标机 cron 安装配置
- 尚未落地真实目标机的长期驻留部署与公网域名接入，这属于后续运维执行动作，不再阻塞 `T1.6`

## 当前开放问题

- 自动发布策略是默认启用还是默认待审核，仍需在实施前确认
- 下载登记将作为阶段三扩展接口预留，是否真正上线统计能力仍需在实施前确认
- 告警渠道采用邮件、Webhook 还是其他方式，仍需在运维实施前确认

## 关键设计决策

- 一期以单机架构落地，不做微服务拆分
- 一期以 SQLite 作为结构化数据存储
- 一期以本地文件系统存储图片资源
- 一期以 cron 负责定时调度，避免过早引入消息队列
- 一期公开前端采用“FastAPI 托管页面骨架 + 原生 HTML/CSS/JavaScript + 只读公开 API”的保守方案
- 一期后台继续采用“FastAPI 托管页面骨架 + 原生 HTML/CSS/JavaScript + 后台 API 驱动”的保守方案
- 内容状态与图片状态必须联动，公开接口只能返回 `enabled`、允许公开展示、资源可用且处于发布时间窗口内的数据
- 手动采集采用“后台提交任务，cron 近实时消费”的保守方案
- 一期后台会话采用数据库持久化模式，服务端只保存会话令牌摘要

## 后续优先级

1. 先进入 `T2.5`，补齐备份恢复和恢复演练
2. 再补齐目标机 cron 安装与计划配置
3. 最后开展阶段三能力扩展
