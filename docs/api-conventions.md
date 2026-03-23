# BingWall API 约定

## 文档元信息

- 更新时间：2026-03-23T00:00:00Z
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

### 后台接口

- 必须登录
- 必须有会话过期时间
- 必须记录审计日志
- 危险操作必须具备明确操作者身份

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
| `resolution_min_width` | integer | 否 | 最小宽度 |
| `resolution_min_height` | integer | 否 | 最小高度 |
| `sort` | string | 否 | 一期建议支持 `date_desc` |

响应数据结构：

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

响应数据结构：

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
  "width": 1920,
  "height": 1080,
  "source_name": "Bing"
}
```

### 3. 公开筛选项

- 方法：`GET`
- 路径：`/api/public/wallpaper-filters`

响应数据结构：

```json
{
  "markets": [
    {
      "code": "en-US",
      "label": "English (United States)"
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

### 4. 后台登录

- 方法：`POST`
- 路径：`/api/admin/auth/login`

请求体结构：

```json
{
  "username": "admin",
  "password": "plain-text-input"
}
```

响应数据结构：

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

### 5. 后台内容列表

- 方法：`GET`
- 路径：`/api/admin/wallpapers`

请求参数：

- 支持 `content_status`
- 支持 `image_status`
- 支持 `market_code`
- 支持 `created_from_utc`
- 支持 `created_to_utc`

### 6. 后台内容状态切换

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

### 7. 手动采集任务创建

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

响应数据结构：

```json
{
  "task_id": 1001,
  "task_status": "queued"
}
```

### 8. 后台任务列表

- 方法：`GET`
- 路径：`/api/admin/collection-tasks`

请求参数：

- `task_status`
- `trigger_type`
- `source_type`
- `created_from_utc`
- `created_to_utc`

### 9. 后台任务重试

- 方法：`POST`
- 路径：`/api/admin/collection-tasks/{task_id}/retry`

约束：

- 只能重试明确目标任务
- 不允许无筛选条件的批量重试

### 10. 健康检查

#### 存活检查

- 方法：`GET`
- 路径：`/api/health/live`

#### 就绪检查

- 方法：`GET`
- 路径：`/api/health/ready`

#### 深度检查

- 方法：`GET`
- 路径：`/api/health/deep`

## 下载策略约定

- 一期默认使用静态资源直链
- 若需要统计下载行为，可增加“下载登记接口 + 静态资源跳转”折中方案
- 不应让应用服务成为大文件传输主链路

## 接口实施要求

- 所有请求参数都必须定义明确类型和取值范围
- 所有输出结构都应有显式 schema
- 公开接口不得返回后台字段、内部路径和敏感信息
- 后台接口必须保留审计上下文
- 破坏性接口调整必须同步更新本文件和变更日志
