# BingWall API 约定

## 文档元信息

- 更新时间：2026-03-26T12:30:40Z
- 依据文档：`docs/system-design.md`
- 文档定位：公开接口与后台接口的统一契约说明

## 目标

本文件用于约束一期 API 的边界、风格和核心契约，确保后端实现、公开前端和后台管理的联调标准一致。

## 设计原则

- 公开接口和后台接口严格分离
- 除静态文件和特殊下载响应外，统一使用统一响应结构
- 参数必须显式校验，不能依赖隐含结构
- 错误表达采用“HTTP 状态码 + 业务错误码”
- 所有时间字段以 UTC 输出，并使用 ISO 8601 格式

## 路由边界

### 公开接口前缀

- 建议前缀：`/api/public`

用途：

- 列表查询
- 详情查询
- 筛选选项
- 站点基础信息
- 下载入口信息

### 后台接口前缀

- 建议前缀：`/api/admin`

用途：

- 登录与会话
- 内容管理
- 任务管理
- 日志与审计查询
- 手动采集创建和重试

### 健康检查前缀

- 建议前缀：`/api/health`

用途：

- 存活检查
- 就绪检查
- 深度检查

## 统一响应结构

### 成功响应

```json
{
  "success": true,
  "message": "ok",
  "data": {},
  "trace_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "pagination": null
}
```

### 失败响应

```json
{
  "success": false,
  "message": "参数错误",
  "error_code": "COMMON_INVALID_ARGUMENT",
  "data": null,
  "trace_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"
}
```

### 字段说明

| 字段 | 说明 |
|---|---|
| `success` | 是否成功 |
| `message` | 人类可读消息 |
| `data` | 实际业务数据 |
| `trace_id` | 请求追踪标识 |
| `pagination` | 列表分页信息，仅列表接口返回 |
| `error_code` | 业务错误码，仅失败响应返回 |

说明：

- 本文后续“响应数据结构”示例，如无特别说明，均表示统一响应结构中 `data` 字段的内部结构，而不是完整 HTTP 响应包裹对象

## 分页约定

列表接口建议使用页码分页。

请求参数：

- `page`：页码，从 `1` 开始
- `page_size`：每页条数，一期建议默认 `20`，最大 `100`

分页响应示例：

```json
{
  "page": 1,
  "page_size": 20,
  "total": 135,
  "total_pages": 7
}
```

## 鉴权约定

### 公开接口

- 无需登录
- 只能查询可公开数据
- 公开查询默认只返回同时满足以下条件的内容：`content_status = enabled`、`is_public = true`、`image_status = ready`、`resource_status = ready`，且当前时间处于发布时间窗口内
- 若内容不允许下载，公开详情可返回内容本身，但下载地址应为空或不返回

### 后台接口

- 必须登录
- 使用 `Authorization: Bearer <session_token>` 传递当前会话令牌
- 必须有会话过期时间
- 必须记录审计日志
- 危险操作必须具备明确操作者身份
- 一期默认采用数据库持久化会话，服务端仅保存令牌摘要

## 错误码分组建议

| 分组 | 前缀建议 | 说明 |
|---|---|---|
| 公共错误 | `COMMON_` | 参数错误、未找到、冲突等 |
| 公开查询 | `PUBLIC_` | 公开列表、详情、下载入口相关 |
| 后台鉴权 | `ADMIN_AUTH_` | 登录失败、会话失效、权限不足 |
| 内容管理 | `CONTENT_` | 状态流转非法、目标不存在 |
| 采集任务 | `COLLECT_` | 任务创建失败、任务冲突、重试失败 |
| 资源处理 | `RESOURCE_` | 资源未就绪、文件缺失、资源损坏 |
| 系统错误 | `SYSTEM_` | 数据库异常、配置错误、依赖异常 |

## 核心接口契约

以下契约为一期最低要求。

### 1. 公开壁纸列表

- 方法：`GET`
- 路径：`/api/public/wallpapers`

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `page` | integer | 否 | 页码 |
| `page_size` | integer | 否 | 每页数量 |
| `market_code` | string | 否 | 地区筛选 |
| `tag_keys` | string | 否 | 标签稳定键列表，使用半角逗号分隔；多标签按“同时命中”处理 |
| `resolution_min_width` | integer | 否 | 最小宽度 |
| `resolution_min_height` | integer | 否 | 最小高度 |
| `sort` | string | 否 | 一期建议支持 `date_desc` |

响应数据结构（`data` 字段）：

```json
{
  "items": [
    {
      "id": 1,
      "title": "string",
      "subtitle": "string",
      "market_code": "en-US",
      "wallpaper_date": "2026-03-22",
      "thumbnail_url": "/images/bing/2026/03/en-US/example-thumb.jpg",
      "detail_url": "/wallpapers/1"
    }
  ]
}
```

### 2. 公开壁纸详情

- 方法：`GET`
- 路径：`/api/public/wallpapers/{wallpaper_id}`

响应数据结构（`data` 字段）：

```json
{
  "id": 1,
  "title": "string",
  "subtitle": "string",
  "description": "string",
  "copyright_text": "string",
  "market_code": "en-US",
  "wallpaper_date": "2026-03-22",
  "preview_url": "/images/bing/2026/03/en-US/example.jpg",
  "download_url": "/images/bing/2026/03/en-US/example.jpg",
  "is_downloadable": true,
  "width": 1920,
  "height": 1080,
  "source_name": "Bing"
}
```

### 3. 公开筛选项

- 方法：`GET`
- 路径：`/api/public/wallpaper-filters`

响应数据结构（`data` 字段）：

```json
{
  "markets": [
    {
      "code": "en-US",
      "label": "English (United States)"
    }
  ],
  "tags": [
    {
      "id": 1,
      "tag_key": "theme_forest",
      "tag_name": "森林",
      "tag_category": "theme"
    }
  ],
  "sort_options": [
    {
      "value": "date_desc",
      "label": "最新优先"
    }
  ]
}
```

### 4. 站点基础信息

- 方法：`GET`
- 路径：`/api/public/site-info`

响应数据结构（`data` 字段）：

```json
{
  "site_name": "BingWall",
  "site_description": "Bing 壁纸图片服务",
  "default_market_code": "en-US"
}
```

### 5. 后台登录

- 方法：`POST`
- 路径：`/api/admin/auth/login`

请求体结构：

```json
{
  "username": "admin",
  "password": "plain-text-input"
}
```

响应数据结构（`data` 字段）：

```json
{
  "session_token": "opaque-token",
  "expires_at_utc": "2026-03-23T01:00:00Z",
  "user": {
    "id": 1,
    "username": "admin",
    "role_name": "super_admin"
  }
}
```

说明：

- `session_token` 为一次性返回的会话令牌，服务端仅保存其摘要
- 登录成功后必须同时写入登录审计记录和会话记录

### 5.1 后台登出

- 方法：`POST`
- 路径：`/api/admin/auth/logout`

请求头：

- `Authorization: Bearer <session_token>`

响应数据结构（`data` 字段）：

```json
{
  "revoked": true
}
```

约束：

- 必须基于当前登录会话执行
- 成功后必须使当前会话立即失效
- 必须写入审计日志

### 6. 后台内容列表

- 方法：`GET`
- 路径：`/api/admin/wallpapers`

请求参数：

- 支持 `content_status`
- 支持 `image_status`
- 支持 `market_code`
- 支持 `created_from_utc`
- 支持 `created_to_utc`

响应数据结构（`data.items[*]`）至少包含：

- `id`
- `title`
- `market_code`
- `wallpaper_date`
- `source_type`
- `source_name`
- `content_status`
- `resource_status`
- `image_status`
- `is_public`
- `is_downloadable`
- `preview_url`
- `width`、`height`
- `failure_reason`
- `created_at_utc`
- `updated_at_utc`

### 7. 后台内容详情

- 方法：`GET`
- 路径：`/api/admin/wallpapers/{wallpaper_id}`

响应数据结构（`data` 字段）应至少包含：

- 展示字段
- 来源字段
- 资源信息
- 当前状态
- 失败原因
- 最近操作记录

当前实现会返回以下核心字段：

- 展示字段：`title`、`subtitle`、`description`、`copyright_text`、`location_text`
- 来源字段：`source_type`、`source_name`、`source_key`、`market_code`、`wallpaper_date`、`published_at_utc`
- 资源信息：`resource_relative_path`、`preview_url`、`resource_type`、`storage_backend`、`mime_type`、`file_size_bytes`、`width`、`height`、`origin_page_url`、`origin_image_url`
- 当前状态：`content_status`、`resource_status`、`image_status`、`is_public`、`is_downloadable`、`deleted_at_utc`
- 最近操作记录：`recent_operations[*].admin_username`、`action_type`、`before_state`、`after_state`、`trace_id`、`created_at_utc`

### 8. 后台内容状态切换

- 方法：`POST`
- 路径：`/api/admin/wallpapers/{wallpaper_id}/status`

请求体结构：

```json
{
  "target_status": "enabled",
  "operator_reason": "人工审核通过"
}
```

约束：

- 非法状态流转必须返回明确错误码
- 必须写入审计日志
- 当前实现仅支持 `enabled`、`disabled`、`deleted` 三个目标状态
- 当前实现允许 `draft -> enabled`、`enabled -> disabled`、`disabled -> enabled`、任意非删除状态 `-> deleted`
- 当目标状态为 `enabled` 时，必须同时满足 `resource_status = ready` 且默认资源 `image_status = ready`

### 9. 手动采集任务创建

- 方法：`POST`
- 路径：`/api/admin/collection-tasks`

请求体结构：

```json
{
  "source_type": "bing",
  "market_code": "en-US",
  "date_from": "2026-03-22",
  "date_to": "2026-03-22",
  "force_refresh": false
}
```

响应数据结构（`data` 字段）：

```json
{
  "task_id": 1001,
  "task_status": "queued"
}
```

约束：

- 当前实现仅支持 `source_type = bing`
- `date_from` 与 `date_to` 必须满足 `date_from <= date_to`
- 当前 Bing 手动采集仅支持最近 `8` 天内、且跨度不超过 `8` 天的日期范围
- 当前实现会记录 `force_refresh` 请求参数，但仍继续沿用一期既有去重规则，不直接覆盖已存在内容

### 10. 后台任务列表

- 方法：`GET`
- 路径：`/api/admin/collection-tasks`

请求参数：

- `task_status`
- `trigger_type`
- `source_type`
- `created_from_utc`
- `created_to_utc`

响应数据结构（`data.items[*]`）至少包含：

- `id`
- `task_type`
- `source_type`
- `trigger_type`
- `triggered_by`
- `task_status`
- `market_code`
- `date_from`
- `date_to`
- `force_refresh`
- `success_count`
- `duplicate_count`
- `failure_count`
- `error_summary`
- `retry_of_task_id`
- `created_at_utc`

### 11. 后台任务详情

- 方法：`GET`
- 路径：`/api/admin/collection-tasks/{task_id}`

响应数据结构（`data` 字段）应至少包含：

- 任务基本信息
- 成功数、重复数、失败数
- 错误摘要
- 逐条处理明细
- 请求参数快照

### 12. 后台任务重试

- 方法：`POST`
- 路径：`/api/admin/collection-tasks/{task_id}/retry`

约束：

- 只能重试明确目标任务
- 不允许无筛选条件的批量重试
- 当前实现仅允许重试 `failed` 或 `partially_failed` 的任务

### 13. 后台日志查询

- 方法：`GET`
- 路径：`/api/admin/logs`

请求参数至少应支持：

- `task_id`
- `error_type`
- `started_from_utc`
- `started_to_utc`

说明：

- 一期该接口主要查询采集任务的结构化处理日志，基础数据来源为 `collection_task_items`
- 如需联动应用文本日志，应返回日志摘要或定位信息，不直接暴露服务器原始日志文件路径
- 当前实现会返回 `task_id`、`task_status`、`source_type`、`trigger_type`、`action_name`、`result_status`、`failure_reason` 和结构化定位字段

### 14. 后台审计记录查询

- 方法：`GET`
- 路径：`/api/admin/audit-logs`

请求参数至少应支持：

- `admin_user_id`
- `target_type`
- `target_id`
- `started_from_utc`
- `started_to_utc`

响应数据结构（`data.items[*]`）至少包含：

- `id`
- `admin_user_id`
- `admin_username`
- `action_type`
- `target_type`
- `target_id`
- `before_state`
- `after_state`
- `request_source`
- `trace_id`
- `created_at_utc`

### 15. 健康检查

#### 存活检查

- 方法：`GET`
- 路径：`/api/health/live`
- 约束：仅用于确认进程可响应，成功时返回 `200`

#### 就绪检查

- 方法：`GET`
- 路径：`/api/health/ready`
- 约束：响应至少包含配置状态、数据库状态和关键目录访问状态
- 约束：当数据库未就绪、关键目录缺失或不可访问时，必须返回 `503`

#### 深度检查

- 方法：`GET`
- 路径：`/api/health/deep`
- 约束：响应至少包含最近一次采集任务摘要、磁盘使用情况、资源目录摘要和最近一次恢复验证记录摘要
- 约束：当数据库或关键目录不可用，或磁盘使用率超过阈值时，必须返回 `503`
- 约束：当最近一次采集任务失败、部分失败或系统尚未产生采集任务时，可返回 `200`，但 `status` 应标记为 `degraded`
- 最近一次恢复验证记录摘要至少应包含：恢复验证 ID、对应备份快照 ID、验证状态、验证时间、深度健康状态和验证记录路径

## 阶段三扩展接口预留

以下接口中，标签相关能力已在 `T3.1` 落地；其余阶段三接口仍作为后续扩展预留。

### 标签查询与维护

#### 公开标签筛选项

- 方法：`GET`
- 路径：`/api/public/tags`

响应数据结构（`data` 字段）：

```json
{
  "items": [
    {
      "id": 1,
      "tag_key": "theme_forest",
      "tag_name": "森林",
      "tag_category": "theme"
    }
  ]
}
```

约束：

- 仅返回可公开使用且状态为 `enabled` 的标签
- 响应应包含标签 ID、名称、稳定键和分类

#### 后台标签列表

- 方法：`GET`
- 路径：`/api/admin/tags`

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `status` | string | 否 | 标签状态，支持 `enabled`、`disabled` |
| `tag_category` | string | 否 | 标签分类精确筛选 |

#### 后台标签创建与更新

- 方法：`POST` / `PATCH`
- 路径：`/api/admin/tags`、`/api/admin/tags/{tag_id}`

请求体字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tag_key` | string | 创建必填 | 稳定机器键，当前实现会统一转为小写 |
| `tag_name` | string | 创建必填 | 展示名称 |
| `tag_category` | string | 否 | 标签分类 |
| `status` | string | 否 | 标签状态，支持 `enabled`、`disabled` |
| `sort_weight` | integer | 否 | 排序权重，值越大越靠前 |
| `operator_reason` | string | 是 | 后台操作原因，会写入审计日志 |

约束：

- `tag_key` 必须唯一
- `tag_key` 仅允许稳定 ASCII 字符，支持字母、数字、下划线和连字符
- 停用标签后不得继续出现在公开筛选项中

#### 后台内容标签绑定

- 方法：`PUT`
- 路径：`/api/admin/wallpapers/{wallpaper_id}/tags`

请求体结构：

```json
{
  "tag_ids": [1, 2, 3],
  "operator_reason": "补充主题标签"
}
```

### 下载登记

#### 公开下载登记

- 方法：`POST`
- 路径：`/api/public/download-events`

请求体结构：

```json
{
  "wallpaper_id": 1,
  "resource_id": 10,
  "download_channel": "public_detail"
}
```

响应数据结构（`data` 字段）：

```json
{
  "redirect_url": "/images/bing/2026/03/en-US/example.jpg",
  "event_id": 5001
}
```

约束：

- 下载登记接口只负责记录事件与返回跳转地址，不直接传输大文件
- 登记失败时应返回明确错误码，或在降级策略下记录日志后继续返回静态资源地址
- 下载统计不得暴露客户端原始 IP

## 下载策略约定

- 一期默认使用静态资源直链
- 若需要统计下载行为，可增加“下载登记接口 + 静态资源跳转”折中方案；推荐接口为 `POST /api/public/download-events`
- 不应让应用服务成为大文件传输主链路

## 接口实施要求

- 所有请求参数都必须定义明确类型和取值范围
- 所有输出结构都应有显式 schema
- 公开接口不得返回后台字段、内部路径和敏感信息
- 后台接口必须保留审计上下文
- 破坏性接口调整必须同步更新本文件和变更日志
