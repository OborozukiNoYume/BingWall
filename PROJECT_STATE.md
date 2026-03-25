# PROJECT_STATE

## 文档元信息

- 更新时间：2026-03-25T12:27:30Z
- 当前阶段：阶段一已完成，下一优先级为阶段二 `T2.1`
- 状态说明：仓库已完成一期系统设计总纲、配套文档骨架、经系统级校准的阶段路线图，并已落地 `T1.1` 的最小后端工程骨架、`T1.2` 的 SQLite 迁移基线、`T1.3` 的 Bing 采集、去重、任务记录、图片下载与资源入库主链路、`T1.4` 的公开 API 最小集、`T1.5` 的基础公开前端，以及 `T1.6` 的单机部署模板、运行说明与自动化部署验收

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

- 已提供 `make setup`、`make db-migrate`、`make collect-bing`、`make verify`、`make verify-deploy`、`make run` 统一命令入口
- 已提供 `/api/health/live` 最小健康检查接口
- 已提供 `/api/public/wallpapers`、`/api/public/wallpaper-filters`、`/api/public/site-info` 和 `/api/public/wallpapers/{wallpaper_id}` 公开接口
- 已提供 `/`、`/wallpapers` 和 `/wallpapers/{wallpaper_id}` 公开页面
- 已提供 `/assets/*` 页面静态资源和 `/images/*` 本地开发图片访问挂载
- 已提供 SQLite 数据库初始化命令
- 已提供 `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 和 `deploy/systemd/bingwall.env.example` 单机部署模板
- 已提供 `scripts/verify_t1_6.py`，可在不改写系统级服务配置的前提下执行 `T1.6` 自动化部署验收
- 已生成运行时版本锁定文件和 Python 依赖锁定文件

后续要求：

- 阶段二开始前，仍需补齐 `/api/health/ready`、`/api/health/deep` 与 cron 任务

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

## 未完成内容

- 尚未落地后台 API
- 尚未实现后台登录、手动任务消费 cron、就绪/深度健康检查、备份恢复
- 尚未落地真实目标机的长期驻留部署与公网域名接入，这属于后续运维执行动作，不再阻塞 `T1.6`

## 当前开放问题

- 管理后台的具体实现技术尚未在仓库内定稿
- 自动发布策略是默认启用还是默认待审核，仍需在实施前确认
- 下载登记将作为阶段三扩展接口预留，是否真正上线统计能力仍需在实施前确认
- 告警渠道采用邮件、Webhook 还是其他方式，仍需在运维实施前确认

## 关键设计决策

- 一期以单机架构落地，不做微服务拆分
- 一期以 SQLite 作为结构化数据存储
- 一期以本地文件系统存储图片资源
- 一期以 cron 负责定时调度，避免过早引入消息队列
- 一期公开前端采用“FastAPI 托管页面骨架 + 原生 HTML/CSS/JavaScript + 只读公开 API”的保守方案
- 内容状态与图片状态必须联动，公开接口只能返回 `enabled`、允许公开展示、资源可用且处于发布时间窗口内的数据
- 手动采集采用“后台提交任务，cron 近实时消费”的保守方案
- 一期后台会话采用数据库持久化模式，服务端只保存会话令牌摘要

## 后续优先级

1. 先进入 `T2.1`，完成管理员认证与会话控制
2. 再进入 `T2.2`，完成后台内容管理 API 与页面
3. 最后开展阶段二、阶段三能力补齐
