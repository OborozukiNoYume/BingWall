# BingWall 部署与运行说明

## 文档元信息

- 更新时间：2026-03-25T13:55:53Z
- 依据文档：`docs/system-design.md`
- 文档定位：一期单机部署、配置、运行、备份与恢复要求说明

## 当前状态说明

当前仓库已包含阶段一 `T1.1` 的最小可执行后端骨架、阶段一 `T1.2` 的 SQLite 迁移基线、阶段一 `T1.3` 的 Bing 采集与资源入库主链路、阶段一 `T1.4` 的公开 API、阶段一 `T1.5` 的基础公开前端、阶段一 `T1.6` 的单机部署模板与自动化部署验收入口，以及阶段二 `T2.3` 的手动采集任务消费入口与后台观测页面、阶段二 `T2.4` 的健康检查与资源巡检闭环。本文件继续记录一期实施时必须遵循的部署与运行要求，并补充可直接复用的部署模板位置。

## 1. 部署目标

一期采用单机部署，目标是以最小复杂度打通以下链路：

- Nginx 提供前端静态资源和图片资源
- FastAPI 提供公开 API、后台 API 和健康检查接口
- SQLite 保存结构化数据
- 本地文件系统保存图片资源
- systemd 托管应用进程
- cron 触发定时采集、任务消费、巡检和备份

## 2. 目标环境

以下内容为一期实施时必须固定并记录的运行时基线要求。当前仓库已具备最小可执行后端代码和数据库迁移基线，因此本节记录已确认版本与后续仍需补齐的部署侧锁定动作。

| 组件 | 当前记录 | 说明 |
|---|---|---|
| Ubuntu | `24.04 LTS` 目标平台 | 部署环境需在实施时记录精确发行版本 |
| Python | `3.14.2` | 当前开发基线，后续需写入运行时和依赖管理文件 |
| Node.js | `24.13.0` | 当前前端与构建运行时基线，后续如引入 Node.js 构建链路需补充版本锁定文件 |
| SQLite | 待实施环境安装后记录精确版本 | 一期数据库 |
| Nginx | 待实施环境安装后记录精确版本 | 反向代理与静态资源服务 |
| systemd | 当前工作环境可见为 `255.4-1ubuntu8.12` | 进程托管 |
| cron | 待实施环境安装后记录精确版本 | 定时触发 |

说明：

- 当前仓库已生成 `.python-version`、`.nvmrc` 和 `requirements.lock.txt`
- 当前仓库已生成 `deploy/nginx/bingwall.conf`、`deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 与 `deploy/systemd/bingwall.env.example`
- 当前已确认 `Python 3.14.2` 为一期开发基线，阶段一初始化代码时必须围绕该版本生成运行时与依赖锁定文件
- 当前已确认 `Node.js 24.13.0` 为前端与构建运行时基线；若后续引入 Node.js 构建链路，必须补充对应版本锁定文件
- SQLite、Nginx、cron 的精确版本必须在目标部署环境创建时记录到部署清单

## 3. 目录约定

一期建议采用以下目录约定：

| 目录 | 作用 |
|---|---|
| `/opt/bingwall/app` | 应用代码目录 |
| `/var/lib/bingwall/data` | SQLite 数据目录 |
| `/var/lib/bingwall/images/tmp` | 临时下载目录 |
| `/var/lib/bingwall/images/public` | 正式资源目录 |
| `/var/lib/bingwall/images/failed` | 失败隔离目录 |
| `/var/log/bingwall` | 应用和任务日志目录 |
| `/var/backups/bingwall` | 备份目录 |
| `/etc/bingwall` | 受控配置目录 |

### 目录权限建议

为满足“应用写入、Nginx 读取”的最小要求，建议按以下方式创建目录：

- `/opt/bingwall/app`：代码目录，建议 `bingwall:bingwall`
- `/var/lib/bingwall/data`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/tmp`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/failed`：仅应用可读写，建议 `0750`，`bingwall:bingwall`
- `/var/lib/bingwall/images/public`：应用写入、Nginx 读取，建议 `2750`，`bingwall:www-data`
- `/var/log/bingwall`：应用日志和 Nginx 日志目录，建议 `0750`
- `/etc/bingwall`：受控配置目录，建议 `0750`，仅运维与应用账户可访问

当前仓库提供的 `deploy/systemd/bingwall.tmpfiles.conf` 已按上述口径写出目录模板。

## 4. 配置要求

### 必备配置项

| 类别 | 关键项 |
|---|---|
| 服务配置 | 监听地址、端口、基础 URL |
| 数据库配置 | SQLite 文件路径 |
| 存储配置 | 临时目录、正式目录、备份目录 |
| 采集配置 | 来源开关、市场、超时、重试次数 |
| 安全配置 | 会话密钥、登录过期时间、密码策略 |
| 日志配置 | 级别、目录、保留天数 |
| 告警配置 | 邮件或 Webhook 地址 |

### 关键配置基线

#### 会话密钥

- 必须使用不少于 `32` 字节的高强度随机值
- 必须通过环境变量或受控配置文件注入，不得写入仓库
- 推荐使用 Base64 或十六进制编码，便于部署系统管理

#### 登录会话

- 后台登录会话默认有效期建议不超过 `12` 小时
- 必须支持主动登出和服务端失效
- 服务端只保存会话令牌摘要，不保存明文令牌

#### 密码策略

- 管理员密码最少 `12` 位
- 必须同时包含大写字母、小写字母、数字和特殊字符
- 密码摘要算法在实施时必须固定并记录；一期推荐 `argon2id`

#### 告警阈值

- 连续 `3` 次自动采集失败触发告警
- 最近 `50` 次下载中失败率超过 `20%` 触发告警
- 磁盘使用率超过 `85%` 触发告警
- 最近 `5` 分钟 API `5xx` 比例超过 `5%` 触发告警
- 超过 `24` 小时未产生成功备份触发告警

### 配置原则

- 所有环境差异都必须通过环境变量或受控配置文件注入
- 配置错误应在启动阶段失败
- 任何敏感值都不能写入仓库
- 所有时间相关配置内部按 UTC 处理

## 5. 服务拓扑

### Nginx

负责：

- 公开前端静态资源
- 管理后台静态资源
- 图片正式资源目录
- 反向代理 `/api/*`

不得暴露：

- 临时下载目录
- 配置目录
- 日志目录
- 数据库目录

### FastAPI

负责：

- 公开 API
- 后台 API
- 健康检查接口
- 业务日志输出

### cron

负责：

- 自动采集触发
- 手动采集任务消费
- 失败重试
- 资源巡检
- 备份任务

## 6. 启动与运行要求

当前仓库已具备最小后端服务，因此以下内容分为“当前已提供”和“后续仍需补齐”两部分：

### 后端服务

当前已提供：

- 依赖安装命令：`make setup`
- 数据库初始化命令：`make db-migrate`
- 手动采集命令：`make collect-bing MARKET=en-US COUNT=1`
- 手动采集任务消费命令：`make consume-collection-tasks`
- 资源巡检命令：`make inspect-resources`
- 本地开发验证命令：`make verify`
- 仓库内自动化部署验收命令：`make verify-deploy`
- 本地开发启动命令：`make run`
- 健康检查接口：`GET /api/health/live`、`GET /api/health/ready`、`GET /api/health/deep`
- 生产环境变量示例：`deploy/systemd/bingwall.env.example`
- `systemd` 服务模板：`deploy/systemd/bingwall-api.service`
- 目录权限模板：`deploy/systemd/bingwall.tmpfiles.conf`
- Nginx 路由模板：`deploy/nginx/bingwall.conf`

### 仓库内自动化部署验收

当前仓库额外提供：

- 验收脚本：`scripts/verify_t1_6.py`
- 统一入口：`make verify-deploy`

该验收入口会在不改写系统级 Nginx 和 `/etc/systemd/system` 的前提下，完成以下检查：

- 对正式 `deploy/systemd/bingwall-api.service` 执行离线安全检查
- 对正式 `deploy/systemd/bingwall.tmpfiles.conf` 执行根目录隔离的模板校验
- 使用临时 `systemd --user` 服务拉起 FastAPI，并验证重启后恢复服务
- 使用 Docker 官方 `nginx` 镜像加载正式路由模板，并验证公开页面、公开 API、前端静态资源和图片资源访问
- 观察用户级 `journalctl` 日志和临时 Nginx 访问日志，确认应用启动成功和代理转发成功可区分

说明：

- 验收脚本默认把 Nginx 监听端口改写到临时本地端口 `18080`，避免占用真实 `80` 端口
- 验收脚本不会修改 `/etc/systemd/system`、`/etc/nginx`、`/etc/tmpfiles.d`
- 真实目标机上线前，仍需按本文件的生产步骤安装正式服务配置和真实 Nginx 配置

### 生产环境最小启动步骤

1. 把仓库代码部署到 `/opt/bingwall/app`
2. 使用 `python3.14` 在 `/opt/bingwall/app/.venv` 创建虚拟环境并安装 `pip install -e .`
3. 复制 `deploy/systemd/bingwall.env.example` 到 `/etc/bingwall/bingwall.env`，替换域名、会话密钥和实际路径
4. 使用 `set -a && source /etc/bingwall/bingwall.env && set +a` 导入环境后执行 `.venv/bin/python -m app.repositories.migrations`
5. 安装 `deploy/systemd/bingwall-api.service`、`deploy/systemd/bingwall.tmpfiles.conf` 和 `deploy/nginx/bingwall.conf`
6. 执行 `systemd-tmpfiles --create`、`systemctl enable --now bingwall-api.service`、`nginx -t`、`systemctl reload nginx`

### 生产环境模板说明

#### `deploy/systemd/bingwall-api.service`

- 通过 `/etc/bingwall/bingwall.env` 注入受控环境变量
- 使用 `bingwall` 账号运行应用
- 通过 `SupplementaryGroups=www-data` 配合正式资源目录权限，保证应用写入、Nginx 读取
- 采用 `Restart=on-failure`，在进程异常退出后自动重启

#### `deploy/systemd/bingwall.tmpfiles.conf`

- 统一创建数据库、图片、日志、备份和配置目录
- 正式资源目录使用 `bingwall:www-data` 和 `2750`
- 临时目录、失败目录、数据库目录不对 Nginx 开放

#### `deploy/nginx/bingwall.conf`

- `/api/` 反向代理到 `127.0.0.1:8000`
- `/` 代理公开页面
- `/assets/` 直接读取前端静态资源
- `/images/` 直接读取正式资源目录，不暴露磁盘真实路径给浏览器

### 定时任务

后续必须补齐：

- 自动采集 cron 表达式
- 手动任务消费 cron 表达式
- 巡检 cron 表达式
- 备份 cron 表达式

### 健康检查

当前已提供：

- `GET /api/health/live`：确认进程可响应
- `GET /api/health/ready`：确认配置、数据库和关键目录可用；失败时返回 `503`
- `GET /api/health/deep`：返回最近一次采集任务摘要、磁盘使用率和资源目录摘要；严重异常时返回 `503`
- `make inspect-resources`：巡检数据库就绪资源与正式资源目录的一致性，发现资源缺失时自动刷新资源与内容状态

## 7. 日志要求

所有日志至少应包含：

- UTC 时间戳
- 日志级别
- 追踪 ID
- 模块名
- 事件类型
- 摘要信息

禁止记录：

- 密码
- 会话密钥
- 原始令牌
- 其他敏感凭证

## 8. 备份要求

### 备份对象

- SQLite 数据库文件
- 图片正式资源目录
- 配置文件
- 应用日志和审计日志
- `systemd` 和 Nginx 配置

### 备份频率建议

| 对象 | 频率 | 方式 |
|---|---|---|
| 数据库 | 每日 | 一致性备份 |
| 图片目录 | 每日增量，周期性全量 | 文件级备份 |
| 配置文件 | 变更后立即备份 | 版本留存 |
| 日志 | 每日归档 | 压缩保存 |

### 关键约束

- SQLite 备份必须采用一致性方式
- 数据库与图片目录备份应尽量保持同一时间点语义
- 备份产物必须保留多个周期

## 9. 恢复要求

恢复顺序：

1. 恢复配置文件
2. 恢复数据库
3. 恢复图片资源目录
4. 启动应用
5. 执行资源巡检
6. 验证公开接口、后台接口和静态资源访问

## 10. 上线前检查清单

### 阶段一公开链路最小检查

- 配置文件已审查
- 数据目录和权限已创建
- Nginx 路由已校验
- `systemd` 服务已可启动
- 公开页面、公开 API 和静态资源可访问
- `README.md` 中存在可复制启动说明

建议按以下顺序执行并记录结果：

1. 在仓库根目录执行 `make verify-deploy`
2. 在目标机按本文件“生产环境最小启动步骤”安装正式服务
3. 在目标机执行 `nginx -t`
4. 执行 `curl http://127.0.0.1/api/health/live`
5. 执行 `curl http://127.0.0.1/api/health/ready`
6. 执行 `curl http://127.0.0.1/api/health/deep`
7. 执行 `curl http://127.0.0.1/api/public/site-info`
8. 执行 `curl http://127.0.0.1/`
9. 如已有正式资源，执行 `curl -I http://127.0.0.1/images/<正式资源相对路径>`
10. 执行 `make inspect-resources`
11. 观察 `journalctl -u bingwall-api.service` 与 `/var/log/bingwall/nginx.access.log`

### 完整上线检查（阶段二目标）

- 配置文件已审查
- 数据目录和权限已创建
- 日志目录和备份目录已创建
- Nginx 路由已校验
- `systemd` 服务已可启动
- cron 已加载
- 健康检查可访问
- 首次备份可执行
- 首次手动采集已验证

## 11. 当前已知缺口

- 尚无备份脚本
- 尚未完成目标机 cron 安装与计划配置

补充说明：

- 当前仓库已通过临时 `systemd --user` 服务和 Docker 化 `nginx` 完成 `T1.6` 自动化验收
- 目标机仍需执行真实 Nginx 包安装、systemd 服务安装和公网域名接入，这些属于部署执行动作，不再阻塞阶段一验收

这些缺口必须在阶段一和阶段二实施中逐项关闭。
