# BingWall 数据模型说明

## 文档元信息

- 更新时间：2026-03-23T12:30:47Z
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
| `audit_logs` | 后台操作审计 | 可关联内容、任务等对象 |

## 1. 壁纸主体 `wallpapers`

### 作用

表示一条可管理的壁纸内容，是公开展示和后台管理的核心实体。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `source_type` | string | 是 | 来源类型，一期固定为 `bing` |
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

## 2. 图片资源 `image_resources`

### 作用

表示与壁纸相关的实际文件，为后续多版本资源、缩略图和 OSS 迁移预留空间。

### 建议字段

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---|---|
| `id` | integer / uuid | 是 | 主键 |
| `wallpaper_id` | integer / uuid | 是 | 所属壁纸 ID |
| `resource_type` | string | 是 | 资源类型，如 `original` |
| `storage_backend` | string | 是 | 存储后端，如 `local` |
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
- `relative_path` 必须是系统生成路径，不能接收外部直接输入
- `image_status = ready` 时，文件必须已存在于正式资源目录

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
| `status` | string | 是 | 账号状态 |
| `last_login_at_utc` | datetime | 否 | 最近登录时间 |
| `created_at_utc` | datetime | 是 | 创建时间 |
| `updated_at_utc` | datetime | 是 | 更新时间 |

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
- 公开列表和详情只能返回同时满足以下条件的数据：`content_status = enabled`、`is_public = true`、资源真实状态为 `image_status = ready`，且当前时间处于发布时间窗口内（如设置了开始或结束时间）
- 新采集内容默认 `draft`
- 新资源默认 `pending`
- 资源失败时，关联内容不得进入公开状态
- `is_downloadable = false` 时，内容可以继续公开展示，但下载地址不得返回给公开端
- 已启用内容若资源巡检失败，应自动降级为 `disabled` 或从公开查询排除
- `deleted` 内容不要求立即物理删文件，但必须与公开业务隔离

## 索引建议

### `wallpapers`

- `(source_type, wallpaper_date, market_code)` 唯一索引
- `(content_status, resource_status, wallpaper_date)` 公开查询索引
- `(market_code, wallpaper_date)` 筛选索引
- `(created_at_utc)` 后台排序索引

### `image_resources`

- `(wallpaper_id, resource_type)` 普通索引
- `(image_status, last_processed_at_utc)` 巡检与重试索引
- `(source_url_hash)` 技术辅助去重索引
- `(content_hash)` 后续增强去重索引

### `collection_tasks`

- `(task_status, created_at_utc)` 任务查询索引
- `(trigger_type, created_at_utc)` 后台筛选索引

### `collection_task_items`

- `(task_id, occurred_at_utc)` 明细查询索引
- `(result_status)` 异常筛选索引

## 实施注意事项

- 真正建表时必须通过迁移工具生成版本化迁移脚本
- 锁文件和依赖清单应由工具自动维护，不允许手工编辑
- 接口返回结构应复用本文件中的实体语义，避免字段名来回变化
