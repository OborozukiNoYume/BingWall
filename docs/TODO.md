# BingWall 阶段 TODO 路线图

## 文档元信息

- 更新时间：2026-03-23T12:30:47Z
- 依据文档：`docs/system-design.md`
- 文档定位：按阶段拆解的 TODO、依赖关系、来源映射与验收标准

## 使用说明

- 本文件只对既有路线图做系统级校准，不扩展新功能
- 每条 TODO 都必须同时具备设计依据和专项约束来源
- 依赖关系按“数据与模块基础 → 业务实现 → API → 页面 → 部署/运维”重建
- `status` 仅用于标记校准结果，不表示实现进度

## 依赖拓扑（修正后）

- 阶段一主链路：`T1.1 → T1.2 → T1.3 → T1.4 → T1.5 → T1.6`
- 阶段二后台链路：`T1.2 → T2.1 → T2.2`
- 阶段二任务链路：`T1.3 → T2.1 → T2.3`
- 阶段二运维链路：`T1.6 → T2.4 → T2.5`
- 阶段三标签与搜索链路：`T1.4 → T2.2 → T3.1 → T3.6`
- 阶段三来源与存储链路：`T1.3 → T3.2`，`T1.6 → T3.4`
- 阶段三资源版本链路：`T1.3 → T1.4 → T1.5 → T3.3`
- 阶段三统计链路：`T1.4 → T2.2 → T3.5`

## 优化后的 TODO

## 阶段一：基础闭环

### T1.1（原 TODO-1）

- 名称：初始化后端工程与模块骨架
- 描述：建立一期后端基础目录、统一配置入口、依赖管理、运行时版本锁定和最小应用启动能力，为后续数据、采集和 API 模块提供承载结构。
- source_design：`5.2 总体架构说明`，`5.3 架构分层原则`，`6. 模块划分与职责边界`，`25.1 阶段一：基础闭环`
- source_spec：`docs/module-overview.md#模块总览`，`docs/module-overview.md#建议目录结构`，`docs/deployment-runbook.md#2-目标环境`，`docs/deployment-runbook.md#4-配置要求`，`docs/deployment-runbook.md#6-启动与运行要求`
- 输入：系统设计总纲、模块划分约束、部署环境与配置约束
- 输出：后端工程骨架、统一配置加载入口、运行时版本锁定文件、基础格式化与测试命令、最小可启动应用
- depends_on：无
- 验收标准：
  - 仓库中存在清晰的后端目录结构，且与模块说明文档一致
  - Python 运行时已锁定为单一精确版本，并写入项目管理文件
  - 通过统一配置入口加载配置，缺失关键配置时启动会明确失败
  - 本地执行启动命令后，应用进程可正常启动并返回最小 HTTP 响应
  - 格式化命令和基础测试命令均可执行并返回成功状态
- status：adjusted

### T1.2（原 TODO-2）

- 名称：实现数据库模型与迁移基线
- 描述：将一期核心实体、状态模型、唯一约束和索引建议落成真实数据表和版本化迁移脚本。
- source_design：`8. 数据模型设计`，`9. 状态模型与数据生命周期`，`10. 去重策略`，`23.1 测试范围`，`25.1 阶段一：基础闭环`
- source_spec：`docs/data-model.md#实体关系总览`，`docs/data-model.md#状态模型`，`docs/data-model.md#状态联动规则`，`docs/data-model.md#索引建议`，`docs/data-model.md#实施注意事项`
- 输入：T1.1 的工程骨架、数据模型说明、状态与去重约束
- 输出：版本化迁移脚本、核心数据表、关键索引、初始数据库初始化能力
- depends_on：`T1.1`
- 验收标准：
  - `wallpapers`、`image_resources`、`collection_tasks`、`collection_task_items`、`admin_users`、`audit_logs` 均通过迁移脚本创建
  - `source_type + wallpaper_date + market_code` 唯一约束和关键查询索引已落地
  - 所有时间字段统一按 UTC 存储
  - 在空数据库上执行迁移后，可通过数据库检查看到完整表结构
  - 迁移可重复执行，不需要手工改库
- status：adjusted

### T1.3（原 TODO-3 + TODO-4）

- 名称：实现 Bing 采集、去重与资源入库主链路
- 描述：完成从 Bing 获取元数据、字段规范化、双层去重、任务记录、图片下载、文件校验、资源落库到状态更新的完整采集闭环。
- source_design：`6.1 采集系统`，`7.1 自动采集流程`，`7.5 异常流程`，`10. 去重策略`，`11. 图片资源策略`，`15. 定时任务与调度设计`，`25.1 阶段一：基础闭环`
- source_spec：`docs/module-overview.md#1-采集模块`，`docs/module-overview.md#3-存储模块`，`docs/data-model.md#1-壁纸主体-wallpapers`，`docs/data-model.md#2-图片资源-image_resources`，`docs/data-model.md#3-采集任务-collection_tasks`，`docs/data-model.md#4-采集明细-collection_task_items`，`docs/deployment-runbook.md#3-目录约定`
- 输入：Bing 上游数据、T1.2 数据库结构、临时目录和正式资源目录
- 输出：壁纸记录、资源记录、采集任务记录、采集明细日志、临时文件与正式资源文件
- depends_on：`T1.2`
- 验收标准：
  - 触发一次采集后，数据库中能看到新增的壁纸、资源、任务和任务明细记录
  - 相同来源、日期和地区再次采集时，不会重复创建壁纸内容
  - 图片文件先进入临时目录，校验成功后再进入正式资源目录
  - 下载成功时资源状态更新为 `ready`，下载失败时更新为 `failed`
  - 任务汇总中能观察到成功数、重复数、失败数，失败原因可在日志或任务明细中定位
- status：adjusted

### T1.4（原 TODO-5）

- 名称：实现公开 API 最小集
- 描述：提供公开壁纸列表、详情、筛选和站点基础信息接口，并统一响应结构、分页规则、错误码和公开数据过滤规则。
- source_design：`6.3 API 服务层`，`7.3 公开前端访问流程`，`12. API 设计原则`，`23.2 关键验收项`，`25.1 阶段一：基础闭环`
- source_spec：`docs/module-overview.md#4-公开-api-模块`，`docs/data-model.md#状态联动规则`，`docs/api-conventions.md#统一响应结构`，`docs/api-conventions.md#分页约定`，`docs/api-conventions.md#1-公开壁纸列表`，`docs/api-conventions.md#2-公开壁纸详情`，`docs/api-conventions.md#3-公开筛选项`，`docs/api-conventions.md#4-站点基础信息`
- 输入：T1.2 数据结构、T1.3 已入库的内容与资源、公开查询参数
- 输出：公开列表接口、详情接口、筛选接口、站点基础信息接口、统一错误响应
- depends_on：`T1.2`，`T1.3`
- 验收标准：
  - 列表接口只返回同时满足 `content_status = enabled`、`is_public = true`、资源状态可用且处于发布时间窗口内的数据
  - 详情接口返回标题、说明、版权、地区、日期、资源地址和尺寸信息；当内容不可下载时，不返回下载地址或明确返回不可下载状态
  - 站点基础信息接口可返回站点名称、站点说明和默认地区信息
  - 非法参数请求返回明确的 HTTP 状态码和业务错误码
  - 分页参数生效，响应中可见分页信息
  - 接口访问日志中可关联到请求 `trace_id`
- status：adjusted

### T1.5（原 TODO-6）

- 名称：实现基础公开前端
- 描述：提供首页、列表页、详情页和空状态页面，并通过公开 API 渲染内容，不直接访问数据库或文件系统。
- source_design：`6.4 公开前端`，`7.3 公开前端访问流程`，`13. 公开前端设计`，`25.1 阶段一：基础闭环`
- source_spec：`docs/module-overview.md#6-前端展示模块`，`docs/api-conventions.md#1-公开壁纸列表`，`docs/api-conventions.md#2-公开壁纸详情`，`docs/api-conventions.md#3-公开筛选项`
- 输入：T1.4 公开 API、图片静态资源地址
- 输出：首页、列表页、详情页、空结果页、错误提示页
- depends_on：`T1.4`
- 验收标准：
  - 首页可以看到最新壁纸列表
  - 列表页可使用筛选条件并正确刷新结果
  - 详情页可看到单张壁纸的完整展示信息和下载入口
  - 数据为空、内容不存在、资源不可用时，页面会显示明确提示
  - 前端页面仅通过 API 获取业务数据，不直接访问数据库
- status：adjusted

### T1.6（原 TODO-7）

- 名称：完成公开链路单机部署闭环
- 描述：让公开前端、公开 API、图片静态资源和应用进程在单机环境下形成可运行的部署闭环，并提供最小运行说明。
- source_design：`4. 技术选型与可行性分析`，`5. 系统总体架构`，`17.3 健康检查`，`24. 部署方案`，`25.1 阶段一：基础闭环`
- source_spec：`docs/deployment-runbook.md#1-部署目标`，`docs/deployment-runbook.md#3-目录约定`，`docs/deployment-runbook.md#5-服务拓扑`，`docs/deployment-runbook.md#6-启动与运行要求`，`docs/deployment-runbook.md#10-上线前检查清单`
- 输入：T1.5 公开页面、T1.4 公开 API、正式资源目录、部署配置
- 输出：Nginx 路由配置、systemd 服务配置、最小启动说明、公开链路可访问环境
- depends_on：`T1.5`
- 验收标准：
  - 通过 Nginx 可以访问公开页面、公开 API 和图片静态资源
  - FastAPI 进程由 systemd 托管，并支持重启后恢复服务
  - 资源目录权限满足应用写入和 Nginx 读取
  - `README.md` 中存在可复制的启动说明
  - `docs/deployment-runbook.md` 中“阶段一公开链路最小检查”项可逐项验证通过
  - 部署日志中可区分应用启动成功和代理转发成功
- status：adjusted

## 阶段二：后台管理与运维补齐

### T2.1（原 TODO-8）

- 名称：实现管理员认证与会话控制
- 描述：提供后台登录、会话过期控制和基础鉴权能力，为后台管理接口和页面提供统一入口。
- source_design：`6.5 管理后台`，`8.7 管理员账号与审计日志`，`14.1 目标`，`20.2 核心安全要求`，`25.2 阶段二：后台管理与运维补齐`
- source_spec：`docs/module-overview.md#5-后台-api-模块`，`docs/module-overview.md#7-管理后台模块`，`docs/data-model.md#5-管理员账号-admin_users`，`docs/api-conventions.md#鉴权约定`，`docs/api-conventions.md#5-后台登录`
- 输入：T1.2 管理员账号表、后台登录请求、安全配置
- 输出：后台登录接口、会话校验能力、登录失败处理、鉴权上下文
- depends_on：`T1.2`
- 验收标准：
  - 正确账号密码登录后，接口返回会话令牌和过期时间
  - 错误账号或密码登录时，不返回会话令牌，并返回统一错误码
  - 数据库存储的是密码摘要，不存明文密码
  - 会话过期后访问后台接口会被拒绝
  - 登录行为可在后台日志或审计记录中观察到
- status：adjusted

### T2.2（原 TODO-9）

- 名称：实现后台内容管理 API 与页面
- 描述：提供后台内容列表、详情、状态切换、逻辑删除和审计查询能力，并通过后台 API 驱动管理页面，不允许后台页面绕过 API。
- source_design：`7.4 后台管理流程`，`9. 状态模型与数据生命周期`，`14.2 核心页面`，`14.3 后台操作原则`，`25.2 阶段二：后台管理与运维补齐`
- source_spec：`docs/module-overview.md#5-后台-api-模块`，`docs/module-overview.md#7-管理后台模块`，`docs/data-model.md#状态模型`，`docs/data-model.md#6-审计日志-audit_logs`，`docs/api-conventions.md#6-后台内容列表`，`docs/api-conventions.md#7-后台内容详情`，`docs/api-conventions.md#8-后台内容状态切换`，`docs/api-conventions.md#14-后台审计记录查询`
- 输入：T2.1 后台鉴权上下文、内容与资源数据、后台操作命令
- 输出：后台内容管理接口、内容详情接口、审计查询接口、内容管理页面、状态变更结果、审计日志
- depends_on：`T2.1`
- 验收标准：
  - 登录后可在后台页面看到内容列表和内容详情
  - 启用、禁用和逻辑删除均通过后台 API 完成，并返回明确结果
  - 非法状态流转会被拦截，并返回明确错误码
  - 每次状态变更都会生成审计日志，且可关联操作者和目标对象
  - 后台可按对象或时间范围查询审计记录
  - 被禁用或删除的内容不会再出现在公开列表接口中
- status：adjusted

### T2.3（原 TODO-10 + TODO-11）

- 名称：实现手动采集任务与后台观测
- 描述：提供手动采集任务创建、任务消费、任务详情、任务重试、日志查询和后台任务观测能力，并保证任务状态和失败原因可定位。
- source_design：`7.2 手动采集流程`，`14.2 核心页面`，`15. 定时任务与调度设计`，`16. 异常处理策略`，`25.2 阶段二：后台管理与运维补齐`
- source_spec：`docs/module-overview.md#5-后台-api-模块`，`docs/module-overview.md#7-管理后台模块`，`docs/data-model.md#3-采集任务-collection_tasks`，`docs/data-model.md#4-采集明细-collection_task_items`，`docs/api-conventions.md#9-手动采集任务创建`，`docs/api-conventions.md#10-后台任务列表`，`docs/api-conventions.md#11-后台任务详情`，`docs/api-conventions.md#12-后台任务重试`，`docs/api-conventions.md#13-后台日志查询`
- 输入：T2.1 鉴权信息、T1.3 采集执行链路、手动采集参数、cron 消费触发
- 输出：手动采集任务接口、任务列表与详情接口、日志查询接口、后台任务页面、重试结果、失败摘要
- depends_on：`T1.3`，`T2.1`
- 验收标准：
  - 后台可以提交手动采集任务，任务创建后状态为 `queued`
  - cron 能消费待执行任务，并将状态更新为运行中、成功、部分失败或失败
  - 后台页面可看到任务成功数、重复数、失败数和错误摘要
  - 任务重试必须指定明确任务 ID，且重试结果可追踪
  - 逐条处理明细可查询，失败原因可在后台任务详情或日志查询中定位
- status：adjusted

### T2.4（原 TODO-12）

- 名称：实现健康检查与资源巡检
- 描述：提供服务存活、就绪和深度健康检查，并实现数据库记录与资源文件一致性巡检。
- source_design：`16. 异常处理策略`，`17. 日志、监控与健康检查`，`25.2 阶段二：后台管理与运维补齐`
- source_spec：`docs/module-overview.md#8-调度与运维模块`，`docs/data-model.md#状态联动规则`，`docs/api-conventions.md#15-健康检查`，`docs/deployment-runbook.md#6-启动与运行要求`，`docs/deployment-runbook.md#7-日志要求`，`docs/deployment-runbook.md#10-上线前检查清单`
- 输入：T1.6 已部署公开链路、T2.3 最近任务状态、数据库连接、资源目录
- 输出：`/api/health/live`、`/api/health/ready`、`/api/health/deep` 接口、资源巡检脚本、巡检结果日志
- depends_on：`T1.6`，`T2.3`
- 验收标准：
  - `live` 接口能确认进程可响应
  - `ready` 接口能确认数据库和关键目录可访问
  - `deep` 接口能返回最近一次采集状态和磁盘状态摘要
  - 巡检发现资源丢失时，会将对应内容从公开查询中排除或下线
  - 巡检结果和健康检查结果可在日志中观察到
- status：adjusted

### T2.5（原 TODO-13）

- 名称：实现备份与恢复流程
- 描述：建立数据库、资源目录、配置与日志的备份恢复能力，并验证恢复后公开与后台链路可继续使用。
- source_design：`17.3 健康检查`，`21. 存储、备份与恢复`，`24.4 上线检查清单`，`25.2 阶段二：后台管理与运维补齐`
- source_spec：`docs/module-overview.md#8-调度与运维模块`，`docs/deployment-runbook.md#8-备份要求`，`docs/deployment-runbook.md#9-恢复要求`，`docs/deployment-runbook.md#10-上线前检查清单`
- 输入：T1.6 已部署环境、T2.4 健康检查与巡检能力、数据库文件、资源目录、配置文件
- 输出：备份脚本、恢复手册、恢复验证记录、备份产物
- depends_on：`T2.4`
- 验收标准：
  - 备份产物同时覆盖数据库、正式资源目录和关键配置
  - 数据库备份采用一致性方式，不直接拷贝活跃写入文件
  - 按恢复手册执行后，公开页面、公开 API 和后台 API 均可访问
  - 恢复后执行资源巡检可通过
  - 备份和恢复过程都有独立日志记录
- status：adjusted

## 阶段三：增强能力

### T3.1（原 TODO-14）

- 名称：增加标签体系
- 描述：为内容增加标签关联、后台维护和公开筛选能力，为后续搜索与运营组织提供结构化基础。
- source_design：`8.3 壁纸主体实体`，`13.2 页面组成`，`25.3 阶段三：增强能力`，`27. 标签与搜索`
- source_spec：`docs/data-model.md#1-壁纸主体-wallpapers`，`docs/module-overview.md#4-公开-api-模块`，`docs/module-overview.md#5-后台-api-模块`，`docs/module-overview.md#7-管理后台模块`
- 输入：T1.4 公开 API 基线、T2.2 后台内容管理能力、标签配置
- 输出：标签数据结构、后台标签维护入口、公开标签筛选能力
- depends_on：`T1.4`，`T2.2`
- 验收标准：
  - 单条内容可以绑定多个标签，且标签关系能持久化保存
  - 后台可查看和维护内容标签关系
  - 公开查询可按标签筛选，并返回符合公开状态规则的数据
  - 标签变更后可在后台和公开端观察到一致结果
- status：adjusted

### T3.2（原 TODO-15）

- 名称：扩展多来源采集
- 描述：在保留 Bing 主链路稳定的前提下，为额外图片来源接入统一采集接口和来源标识。
- source_design：`2.1 项目目标`，`8.3 壁纸主体实体`，`8.5 采集任务实体`，`22.1 演进目标`，`25.3 阶段三：增强能力`，`27. 多来源采集`
- source_spec：`docs/data-model.md#1-壁纸主体-wallpapers`，`docs/data-model.md#3-采集任务-collection_tasks`，`docs/module-overview.md#1-采集模块`
- 输入：T1.3 采集主链路、来源配置、新来源上游数据
- 输出：来源抽象、扩展采集实现、带来源标识的内容与任务记录
- depends_on：`T1.3`
- 验收标准：
  - 至少可接入一个 Bing 之外的新来源
  - 新来源和 Bing 的任务、内容记录均可通过 `source_type` 区分
  - Bing 现有采集流程不受影响，重复采集行为保持稳定
  - 任务日志中可以观察到来源类型和处理结果
- status：adjusted

### T3.3（原 TODO-16）

- 名称：完善资源派生版本
- 描述：支持缩略图、详情预览图和下载图等资源类型，并让公开端按页面场景选择合适资源。
- source_design：`11.3 资源版本策略`，`13.4 公开前端性能重点`，`25.3 阶段三：增强能力`，`27. 图片衍生资源`
- source_spec：`docs/data-model.md#2-图片资源-image_resources`，`docs/module-overview.md#1-采集模块`，`docs/module-overview.md#4-公开-api-模块`，`docs/module-overview.md#6-前端展示模块`
- 输入：T1.3 原始资源链路、T1.4 公开 API、T1.5 公开前端页面
- 输出：派生资源生成能力、资源类型区分、前端资源使用策略
- depends_on：`T1.3`，`T1.4`，`T1.5`
- 验收标准：
  - 资源表中可明确区分原图、缩略图和预览图
  - 列表页默认使用缩略图，不直接加载原图
  - 详情页可区分预览图和下载图
  - 派生资源生成失败时，可在日志或后台看到失败原因
- status：adjusted

### T3.4（原 TODO-17）

- 名称：适配 OSS 与 CDN
- 描述：将资源定位从本地文件语义扩展为可兼容本地和对象存储的统一方式，并支持迁移期间新旧资源共存。
- source_design：`11.4 图片访问策略`，`21. 存储、备份与恢复`，`22.4 从本地文件迁移到 OSS 的关注点`，`25.3 阶段三：增强能力`，`27. OSS 与 CDN`
- source_spec：`docs/data-model.md#2-图片资源-image_resources`，`docs/api-conventions.md#下载策略约定`，`docs/deployment-runbook.md#3-目录约定`，`docs/deployment-runbook.md#8-备份要求`
- 输入：T1.3 资源记录与文件、T1.6 已部署资源访问链路、对象存储配置
- 输出：存储后端抽象、统一资源定位方式、兼容本地与 OSS 的访问能力
- depends_on：`T1.6`，`T3.2`
- 验收标准：
  - `storage_backend` 能区分本地与 OSS 资源
  - 迁移期间本地资源和 OSS 资源可以同时对外提供访问
  - 公开下载地址不暴露服务器磁盘路径
  - 切换存储后，公开页面中的资源访问不出现中断
- status：adjusted

### T3.5（原 TODO-18）

- 名称：增加下载统计与分析
- 描述：在不让应用服务承担大文件传输主链路的前提下，记录下载行为并输出基础统计结果。
- source_design：`11.4 图片访问策略`，`17.2 指标建议`，`25.3 阶段三：增强能力`，`27. 下载统计与内容分析`
- source_spec：`docs/api-conventions.md#下载策略约定`，`docs/module-overview.md#4-公开-api-模块`，`docs/module-overview.md#5-后台-api-模块`，`docs/module-overview.md#7-管理后台模块`
- 输入：T1.4 公开 API、T2.2 后台管理能力、下载登记事件
- 输出：下载登记能力、基础统计接口或页面、下载趋势视图
- depends_on：`T1.4`，`T2.2`
- 验收标准：
  - 下载动作会生成可追踪的登记记录
  - 后台可以看到基础下载统计结果或趋势视图
  - 下载统计链路与静态资源传输链路分离，应用服务不直接承担大文件主传输
  - 统计结果可通过日志或后台页面观测
- status：adjusted

### T3.6（原 TODO-19）

- 名称：增强搜索能力
- 描述：在现有筛选基础上增加关键词搜索，并保证公开端和后台端的状态过滤规则保持一致。
- source_design：`8.3 壁纸主体实体`，`12.5 查询与筛选原则`，`25.3 阶段三：增强能力`，`27. 标签与搜索`
- source_spec：`docs/data-model.md#1-壁纸主体-wallpapers`，`docs/module-overview.md#4-公开-api-模块`，`docs/module-overview.md#5-后台-api-模块`
- 输入：T3.1 标签体系、T1.4 公开 API 基线、T2.2 后台内容管理能力、关键词字段
- 输出：关键词搜索能力、公开搜索接口、后台搜索能力
- depends_on：`T3.1`，`T2.2`
- 验收标准：
  - 公开端可按关键词查询可公开内容
  - 后台可按关键词和状态联合检索内容
  - 搜索结果继续遵循公开状态和后台状态规则
  - 相同关键词在公开端和后台端的结果差异能通过状态规则解释
- status：adjusted

## 问题总结

### invalid 任务列表

- 无

### 调整依赖的任务

- `T1.3`：将采集、去重和资源入库合并为单一主链路，避免采集模块内部顺序被拆散
- `T1.6`：调整为仅依赖公开链路完成后的部署闭环，保持部署任务位于阶段一末端
- `T2.2`：明确后台页面必须通过后台 API 工作，不直接依赖数据库
- `T2.3`：重建为“手动采集任务 + 后台观测”闭环，依赖后台鉴权和采集主链路
- `T2.4`：改为依赖部署闭环和任务链路，确保深度健康检查有可观测对象
- `T2.5`：改为依赖健康检查与巡检能力，保证恢复后可验证
- `T3.1`、`T3.5`、`T3.6`：补齐对后台管理链路的依赖，避免直接跨越后台 API
- `T3.4`：改为依赖多来源采集后的统一资源语义，避免对象存储迁移与来源抽象脱节

### 合并 / 拆分的任务

- 合并：原 `TODO-3` 与 `TODO-4` 合并为 `T1.3`
- 合并：原 `TODO-10` 与 `TODO-11` 合并为 `T2.3`
- 拆分：无新增拆分
