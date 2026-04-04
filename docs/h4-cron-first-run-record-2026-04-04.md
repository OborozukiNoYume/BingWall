# H4 首轮 Cron 闭环验证记录

## 文档元信息

- 更新时间：2026-04-04T09:50:00Z
- 任务编号：`H4`
- 任务名称：完成首轮 `cron` 闭环验证
- 执行日期：`2026-04-04`
- 记录来源：用户提供的真实目标机执行报告
- 验证边界：当前仓库会话未直接登录目标机；以下内容为基于目标机报告回写的执行记录
- 目标机：阿里云 Ubuntu `24.04.2 LTS`
- 公网入口：`http://139.224.235.228:8000`
- 结论：`H4` 已完成

## 部署现状

- 应用目录：`/home/ubuntu/BingWall`
- 服务用户：`ubuntu`
- 环境文件：`/etc/bingwall/bingwall.env`
- 日志目录：`/var/log/bingwall`
- 备份目录：`/home/ubuntu/BingWall/var/backups`
- `uv` 路径：`/home/ubuntu/.local/bin/uv`
- 对外入口：无额外反向代理，由 `uvicorn` 直接监听 `0.0.0.0:8000`

说明：

- 当前目标机目录和用户口径与仓库推荐的 `/opt/bingwall/app` + `bingwall` 用户方案不同
- 该差异不会阻断 `H4` 验收，但会影响 `cron` 安装命令、备份路径与备份脚本参数

## Cron 安装结果

实际安装命令：

```bash
cd /home/ubuntu/BingWall
make install-cron \
  CRON_APP_DIR=/home/ubuntu/BingWall \
  CRON_ENV_FILE=/etc/bingwall/bingwall.env \
  CRON_LOG_DIR=/var/log/bingwall \
  CRON_UV_BIN=/home/ubuntu/.local/bin/uv
```

安装摘要：

- `installed = true`
- `entry_count = 5`
- `template_path = /home/ubuntu/BingWall/deploy/cron/bingwall-cron`
- `backup_path = /var/log/bingwall/crontab.backup.20260404T091149Z.txt`

已安装任务：

1. `15 3 * * *` `create-scheduled-collection-tasks`
2. `* * * * *` `consume-collection-tasks`
3. `45 3 * * *` `inspect-resources`
4. `15 4 * * *` `archive-wallpapers`
5. `45 4 * * *` `backup`

注意：

- 安装脚本覆盖了当前用户原有 `crontab`
- 原有 3 条非 BingWall 任务已通过 `/var/log/bingwall/crontab.backup.20260404T091149Z.txt` 备份，可按需回滚

## 首轮闭环结果

### 1. 创建定时采集任务

- 结果：通过
- 摘要：成功创建 `9` 个任务
- 细分：`8` 个 Bing 市场任务，`1` 个 `NASA APOD` 任务

### 2. 消费任务队列

- 结果：通过
- 摘要：`processed_count = 5`
- 细分：共成功下载 `9` 张图片，无失败项

### 3. 资源巡检

- 结果：通过
- 摘要：`checked_resource_count = 20`
- 细分：`missing_resource_count = 0`，`disabled_wallpaper_count = 0`

### 4. 壁纸归档

- 结果：通过
- 摘要：任务成功执行
- 细分：当前新部署环境无历史资源需要归档，`archived_resource_count = 0`

### 5. 备份

- 结果：通过
- 命令：`uv run --no-sync python scripts/run_backup.py --skip-nginx --skip-tmpfiles`
- 摘要：成功生成 `backup-20260404T094004Z-d0172fd9`
- 关键产物：
  - `var/backups/backup-20260404T094004Z-d0172fd9/manifest.json`
  - `var/backups/backup-20260404T094004Z-d0172fd9/artifacts/bingwall.sqlite3`
  - `var/backups/backup-20260404T094004Z-d0172fd9/artifacts/public-images.tar.gz`
  - `var/backups/backup-20260404T094004Z-d0172fd9/artifacts/service-configs.tar.gz`

说明：

- 当前目标机没有仓库推荐口径下的本地 `nginx` 与 `tmpfiles` 配置文件，因此备份时显式使用 `--skip-nginx --skip-tmpfiles`

## 验收产物

### Crontab

- 已确认存在 5 条 BingWall 计划任务
- 实际内容见 `crontab -l` 输出，以及上文任务列表

### 日志目录

已确认存在以下文件：

- `/var/log/bingwall/api-error.log`
- `/var/log/bingwall/api.log`
- `/var/log/bingwall/consume-collection-tasks.log`
- `/var/log/bingwall/crontab.backup.20260404T091149Z.txt`

补充说明：

- `create-scheduled-collection-tasks.log`、`inspect-resources.log`、`archive-wallpapers.log`、`backup.log` 会在对应 `cron` 计划首次按调度触发后持续追加
- 本次 `H4` 验收通过手工执行 5 类任务完成首轮闭环，因此接受“日志目录已有首轮产物，但非所有文件都由调度自然生成”的状态

### 备份目录

- 已确认存在 `/home/ubuntu/BingWall/var/backups/backup-20260404T094004Z-d0172fd9/manifest.json`

### 深度健康检查

实际检查命令：

```bash
curl -sS http://127.0.0.1:8000/api/health/deep
```

结果摘要：

- `status = healthy`
- 数据库：`./var/data/bingwall.sqlite3`
- `wallpaper_count = 20`
- `collection_task_count = 11`
- 存储目录：`./var/images/public`
- `missing_resources = 0`
- 采集器状态：`bing = ok`，`nasa_apod = ok`

## 风险与后续建议

- 环境文件存在一行未注释的中文描述，Shell 加载时会出现 `/etc/bingwall/bingwall.env:6: command not found` 警告；虽未阻断任务执行，但建议清理
- 当前目标机仍使用 `ubuntu` 用户和仓库内相对路径目录，建议后续评估是否迁移到仓库推荐的专用用户和绝对路径布局
- 建议为 `/var/log/bingwall/*.log` 补齐 `logrotate` 策略
- 建议确认是否需要把原有的 `timestamp_converter.sh` 三条定时任务恢复回 `crontab`
