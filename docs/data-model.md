# BingWall 数据模型说明

## 文档元信息

- 更新时间：2026-03-26T12:30:40Z
- 依据文档：`docs/system-design.md`
- 文档定位：一期实施前的数据实体、字段分组、状态模型、约束和索引说明

## 设计原则

- 数据模型服务于业务闭环，不只保存原始字段
- 所有时间字段统一使用 UTC 存储
- 内容状态与资源状态必须联动
- 迁移必须版本化管理，不允许手工改生产库
- 一期以 SQLite 为主，但字段设计要避免绑定 SQLite 特性

## 实体关系总览

| 实体 | 说明 | 关系 |
|---|---|---|
| `wallpapers` | 壁纸主体内容 | 一对多关联 `image_resources` |
| `image_resources` | 资源文件记录 | 多对一关联 `wallpapers` |
| `collection_tasks` | 一次自动或手动采集任务 | 一对多关联 `collection_task_items` |
| `collection_task_items` | 任务内逐条处理记录 | 多对一关联 `collection_tasks` |
| `admin_users` | 后台管理员账号 | 一对多关联 `audit_logs` |
| `admin_sessions` | 后台登录会话 | 多对一关联 `admin_users` |
| `audit_logs` | 后台操作审计 | 可关联内容、任务等对象 |
| `tags` | 标签定义 | 多对多关联 `wallpapers` |
| `wallpaper_tags` | 内容与标签关联关系 | 多对一关联 `wallpapers` 与 `tags` |
| `download_events` | 下载登记与统计明细 | 多对一关联 `wallpapers` |

## 1. 壁纸主体 `wallpapers`

### 作用

表示一条可管理的壁纸内容，是公开展示和后台管理的核心实体。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `source_type` | string | 是 | 来源类型，当前已支持 `bing`、`nasa_apod` |
| `source_key` | string | 是 | 来源唯一键，用于追踪和去重 |
| `market_code` | string | 是 | 地区代码，例如 `en-US` |
| `wallpaper_date` | date | 是 | 壁纸所属日期 |
| `title` | string | 否 | 标题 |
| `subtitle` | string | 否 | 简述 |
| `copyright_text` | string | 否 | 版权说明 |
| `source_name` | string | 是 | 来源名称 |
| `published_at_utc` | datetime | 否 | 上游发布时间 |
| `location_text` | string | 否 | 拍摄地或主题说明 |
| `description` | text | 否 | 详情描述 |
| `content_status` | string | 是 | 内容状态 |
| `is_public` | boolean | 是 | 是否允许公开展示 |
| `is_downloadable` | boolean | 是 | 是否允许下载 |
| `publish_start_at_utc` | datetime | 否 | 发布开始时间 |
| `publish_end_at_utc` | datetime | 否 | 发布结束时间 |
| `default_resource_id` | integer / uuid | 否 | 默认资源 |
| `origin_page_url` | string | 否 | 原始页面地址 |
| `origin_image_url` | string | 否 | 原始图片地址 |
| `origin_width` | integer | 否 | 原始宽度 |
| `origin_height` | integer | 否 | 原始高度 |
| `resource_status` | string | 是 | 当前可用资源状态快照 |
| `raw_extra_json` | text | 否 | 来源扩展信息 |
| `sort_weight` | integer | 是 | 排序权重，默认 `0` |
| `deleted_at_utc` | datetime | 否 | 逻辑删除时间 |
| `created_at_utc` | datetime | 是 | 创建时间 |
| `updated_at_utc` | datetime | 是 | 更新时间 |

### 约束建议

- 唯一约束：`source_type + wallpaper_date + market_code`
- 非删除内容才能参与公开查询
- 当 `content_status = enabled` 时，`resource_status` 必须为 `ready`
- `resource_status` 由领域服务或巡检任务根据当前对外可用的资源记录同步刷新，不允许由公开接口直接写入
- 当前关键词搜索基于 `title`、`subtitle`、`copyright_text`、`description` 与已绑定标签实现，不单独新增搜索索引表

## 2. 图片资源 `image_resources`

### 作用

表示与壁纸相关的实际文件，为后续多版本资源、缩略图和 OSS 迁移预留空间。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `wallpaper_id` | integer / uuid | 是 | 所属壁纸 ID |
| `resource_type` | string | 是 | 资源类型，当前使用 `original`、`thumbnail`、`preview`、`download` |
| `variant_key` | string | 是 | 同一 `resource_type` 下的分辨率或变体标识；无分辨率区分时固定为空字符串 |
| `storage_backend` | string | 是 | 存储后端，当前支持 `local`、`oss` |
| `relative_path` | string | 是 | 存储相对路径 |
| `filename` | string | 是 | 文件名 |
| `file_ext` | string | 是 | 扩展名 |
| `mime_type` | string | 是 | 文件类型 |
| `file_size_bytes` | integer | 否 | 文件大小 |
| `width` | integer | 否 | 宽度 |
| `height` | integer | 否 | 高度 |
| `source_url` | string | 否 | 下载来源 URL |
| `source_url_hash` | string | 否 | 来源 URL 哈希 |
| `content_hash` | string | 否 | 文件内容哈希 |
| `downloaded_at_utc` | datetime | 否 | 下载完成时间 |
| `integrity_check_result` | string | 否 | 校验结果 |
| `image_status` | string | 是 | 资源状态 |
| `failure_reason` | text | 否 | 失败原因 |
| `last_processed_at_utc` | datetime | 否 | 最近处理时间 |
| `created_at_utc` | datetime | 是 | 创建时间 |
| `updated_at_utc` | datetime | 是 | 更新时间 |

### 约束建议

- 一个壁纸至少应有一个 `original` 类型资源
- 当内容允许下载时，建议同时生成 `download` 资源；公开列表和详情依赖 `thumbnail` / `preview`
- `original`、`thumbnail`、`preview` 当前仍保持单条资源；`download` 允许按不同 `variant_key` 保存多条分辨率资源
- 同一壁纸下 `(resource_type, variant_key)` 组合必须唯一，避免同一种分辨率资源重复入库
- `relative_path` 必须是系统生成路径，不能接收外部直接输入；迁移到 OSS 时继续沿用同一相对路径语义
- `image_status = ready` 时，`storage_backend = local` 的文件必须已存在于正式资源目录；`storage_backend = oss` 的对象键必须可通过统一资源定位方式访问
- 资源状态变化后，必须同步刷新所属 `wallpapers.resource_status` 快照，并更新 `updated_at_utc`

## 3. 采集任务 `collection_tasks`

### 作用

记录一次自动或手动采集的完整执行过程，用于任务可视化、重试和问题追踪。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `task_type` | string | 是 | 任务类型，如 `scheduled_collect` |
| `source_type` | string | 是 | 来源类型 |
| `trigger_type` | string | 是 | 触发方式，如 `cron`、`admin` |
| `triggered_by` | string | 否 | 触发人 |
| `task_status` | string | 是 | 任务状态 |
| `request_snapshot_json` | text | 否 | 请求参数快照 |
| `started_at_utc` | datetime | 否 | 开始时间 |
| `finished_at_utc` | datetime | 否 | 结束时间 |
| `success_count` | integer | 是 | 成功数量 |
| `duplicate_count` | integer | 是 | 重复数量 |
| `failure_count` | integer | 是 | 失败数量 |
| `error_summary` | text | 否 | 错误摘要 |
| `retry_of_task_id` | integer / uuid | 否 | 被重试任务 ID |
| `created_at_utc` | datetime | 是 | 创建时间 |
| `updated_at_utc` | datetime | 是 | 更新时间 |

## 4. 采集明细 `collection_task_items`

### 作用

记录任务内每个候选条目的处理结果，用于定位失败落点。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `task_id` | integer / uuid | 是 | 所属任务 ID |
| `source_item_key` | string | 否 | 候选来源标识 |
| `action_name` | string | 是 | 执行动作 |
| `result_status` | string | 是 | 处理结果 |
| `dedupe_hit_type` | string | 否 | 去重命中类型 |
| `db_write_result` | string | 否 | 数据库写入结果 |
| `file_write_result` | string | 否 | 文件写入结果 |
| `failure_reason` | text | 否 | 失败原因 |
| `occurred_at_utc` | datetime | 是 | 发生时间 |

## 5. 管理员账号 `admin_users`

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `username` | string | 是 | 登录名 |
| `password_hash` | string | 是 | 密码摘要 |
| `role_name` | string | 是 | 角色或权限级别 |
| `status` | string | 是 | 账号状态，仅允许 `enabled`、`disabled` |
| `last_login_at_utc` | datetime | 否 | 最近登录时间 |
| `created_at_utc` | datetime | 是 | 创建时间 |
| `updated_at_utc` | datetime | 是 | 更新时间 |

约束说明：

- `admin_users.status` 当前只允许 `enabled`、`disabled`
- `enabled` 表示允许登录后台；`disabled` 表示账号存在但禁止登录
- 历史库若存在 `active` 等 legacy 值，数据库迁移会先归一化为 `enabled` 或 `disabled`，随后再阻止新的非法状态写入

## 6. 审计日志 `audit_logs`

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `admin_user_id` | integer / uuid | 是 | 操作人 |
| `action_type` | string | 是 | 操作类型 |
| `target_type` | string | 是 | 目标对象类型 |
| `target_id` | string | 是 | 目标对象 ID |
| `before_state_json` | text | 否 | 操作前摘要 |
| `after_state_json` | text | 否 | 操作后摘要 |
| `request_source` | string | 否 | 请求来源 |
| `trace_id` | string | 是 | 追踪 ID |
| `created_at_utc` | datetime | 是 | 发生时间 |

## 7. 管理员会话 `admin_sessions`

### 作用

记录后台登录后的受控会话。一期采用数据库持久化会话，便于单机部署、过期控制和审计追踪。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `admin_user_id` | integer / uuid | 是 | 所属管理员 ID |
| `session_token_hash` | string | 是 | 会话令牌摘要，不存明文令牌 |
| `session_version` | integer | 是 | 会话版本，用于批量失效控制 |
| `issued_at_utc` | datetime | 是 | 签发时间 |
| `expires_at_utc` | datetime | 是 | 过期时间 |
| `revoked_at_utc` | datetime | 否 | 主动登出或失效时间 |
| `last_seen_at_utc` | datetime | 否 | 最近访问时间 |
| `client_ip` | string | 否 | 登录来源 IP 摘要 |
| `user_agent` | string | 否 | 客户端标识摘要 |
| `created_at_utc` | datetime | 是 | 创建时间 |
| `updated_at_utc` | datetime | 是 | 更新时间 |

### 约束建议

- 单条活跃会话必须同时满足 `revoked_at_utc is null` 且 `expires_at_utc > now()`
- 令牌只允许以摘要形式入库，明文仅在登录响应中返回一次
- 管理员账号被禁用后，其未过期会话必须同步失效
- 管理员主动修改密码后，其当前账号已有后台会话必须同步失效，并要求重新登录

## 8. 标签定义 `tags`

### 作用

为内容提供可维护的结构化标签，用于公开筛选、后台运营和后续搜索增强。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `tag_key` | string | 是 | 稳定机器键，唯一 |
| `tag_name` | string | 是 | 展示名称 |
| `tag_category` | string | 否 | 标签分类，如 `theme`、`location` |
| `status` | string | 是 | 标签状态，如 `enabled`、`disabled` |
| `sort_weight` | integer | 是 | 排序权重，默认 `0` |
| `created_at_utc` | datetime | 是 | 创建时间 |
| `updated_at_utc` | datetime | 是 | 更新时间 |

### 约束建议

- `tag_key` 全局唯一，且应使用稳定 ASCII 标识
- `disabled` 标签不得继续出现在公开筛选项中
- 当前公开关键词搜索只匹配启用标签；后台关键词搜索可匹配全部已绑定标签，用于解释公开与后台结果差异

## 9. 内容标签关联 `wallpaper_tags`

### 作用

记录内容与标签的多对多关系。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `wallpaper_id` | integer / uuid | 是 | 壁纸 ID |
| `tag_id` | integer / uuid | 是 | 标签 ID |
| `created_at_utc` | datetime | 是 | 绑定时间 |
| `created_by` | string | 否 | 绑定来源，如 `admin`、`migration` |

### 约束建议

- `wallpaper_id + tag_id` 必须唯一
- 已逻辑删除内容的标签关联不得出现在公开查询结果中

## 10. 下载登记 `download_events`

### 作用

记录下载行为与基础统计明细，用于下载趋势分析，不直接承担文件传输。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `wallpaper_id` | integer / uuid | 是 | 下载内容 ID |
| `resource_id` | integer / uuid | 否 | 对应资源 ID |
| `request_id` | string | 是 | 请求追踪 ID |
| `market_code` | string | 否 | 请求地区 |
| `download_channel` | string | 是 | 下载入口来源，如 `public_detail` |
| `client_ip_hash` | string | 否 | 客户端 IP 摘要 |
| `user_agent` | string | 否 | 客户端标识摘要 |
| `result_status` | string | 是 | 登记结果，如 `redirected`、`blocked`、`degraded` |
| `redirect_url` | string | 否 | 本次登记返回给客户端的静态资源地址 |
| `occurred_at_utc` | datetime | 是 | 发生时间 |
| `created_at_utc` | datetime | 是 | 创建时间 |

### 约束建议

- 下载登记失败不能阻塞静态资源主传输链路，应采用“先登记、失败可降级记录日志”或异步补记策略
- 原始 IP 不得直接落库，应保存脱敏摘要

## 状态模型

### 内容状态 `content_status`

| 状态值 | 含义 | 是否公开可见 |
|---|---|---|
| `draft` | 已入库但未发布 | 否 |
| `enabled` | 已启用，可公开展示 | 是 |
| `disabled` | 已下线，仍保留数据 | 否 |
| `deleted` | 逻辑删除 | 否 |

### 图片状态 `image_status`

| 状态值 | 含义 |
|---|---|
| `pending` | 等待下载、校验或入库 |
| `ready` | 资源可用 |
| `failed` | 下载、校验或写入失败 |

### 任务状态 `task_status`

| 状态值 | 含义 |
|---|---|
| `queued` | 待执行 |
| `running` | 执行中 |
| `succeeded` | 已完成且整体成功 |
| `partially_failed` | 已完成但存在部分失败 |
| `failed` | 整体失败 |

## 状态联动规则

- `image_status` 是资源表的真实状态，`resource_status` 是壁纸表上用于查询优化和展示的资源状态快照；两者语义必须保持一致
- `image_resources` 写入、资源巡检和后台状态变更都必须经过统一领域规则，同步刷新 `resource_status`
- 公开列表和详情只能返回同时满足以下条件的数据：`content_status = enabled`、`is_public = true`、资源真实状态为 `image_status = ready`，且当前时间处于发布时间窗口内（如设置了开始或结束时间）
- 新采集内容在当前默认配置下会在资源全部就绪后自动转为 `enabled` 且 `is_public = true`
- 当 `BINGWALL_COLLECT_AUTO_PUBLISH_ENABLED = false` 时，新采集内容保持 `draft`
- 新资源默认 `pending`
- 资源失败时，关联内容不得进入公开状态
- `is_downloadable = false` 时，内容可以继续公开展示，但下载地址不得返回给公开端
- Bing 当前会把同一壁纸按官方 15 种分辨率口径保存为多条 `download` 资源；公开详情对外返回默认下载地址和完整分辨率列表
- 已启用内容若资源巡检失败，应自动降级为 `disabled` 或从公开查询排除
- 管理员执行“启用”操作前，领域服务必须校验目标内容的 `resource_status = ready`
- `deleted` 内容不要求立即物理删文件，但必须与公开业务隔离

## 索引建议

### `wallpapers`

- `(source_type, wallpaper_date, market_code)` 唯一索引
- `(content_status, resource_status, wallpaper_date)` 公开查询索引
- `(market_code, wallpaper_date)` 筛选索引
- `(created_at_utc)` 后台排序索引

### `image_resources`

- `(wallpaper_id, resource_type, variant_key)` 唯一索引
- `(image_status, last_processed_at_utc)` 巡检与重试索引
- `(source_url_hash)` 技术辅助去重索引
- `(content_hash)` 后续增强去重索引

### `collection_tasks`

- `(task_status, created_at_utc)` 任务查询索引
- `(trigger_type, created_at_utc)` 后台筛选索引

### `collection_task_items`

- `(task_id, occurred_at_utc)` 明细查询索引
- `(result_status)` 异常筛选索引

### `admin_sessions`

- `(admin_user_id, expires_at_utc)` 会话校验索引
- `(session_token_hash)` 唯一索引

### `tags`

- `(tag_key)` 唯一索引
- `(status, sort_weight)` 公开筛选索引

### `wallpaper_tags`

- `(wallpaper_id, tag_id)` 唯一索引
- `(tag_id, wallpaper_id)` 标签反查索引

### `download_events`

- `(wallpaper_id, occurred_at_utc)` 内容下载趋势索引
- `(resource_id, occurred_at_utc)` 资源版本下载索引
- `(result_status, occurred_at_utc)` 下载结果趋势索引
- `(market_code, occurred_at_utc)` 地区维度统计索引

## 实施注意事项

- 真正建表时必须通过迁移工具生成版本化迁移脚本
- 锁文件和依赖清单应由工具自动维护，不允许手工编辑
- 接口返回结构应复用本文件中的实体语义，避免字段名来回变化
- 阶段二与阶段三新增实体应通过独立迁移脚本增量落地，不应回写修改阶段一已上线表的历史语义
