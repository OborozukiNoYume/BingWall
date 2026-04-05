# BingWall 运维执行记录模板

## 文档元信息

- 更新时间：2026-04-05T03:46:34Z
- 文档定位：关键运维动作的固定记录模板与填写约束
- 适用范围：一期单机部署、真实目标机运维、恢复演练与入口切换

## 使用约定

- 每次执行部署、恢复演练、`cron` 首轮闭环验证、域名切换或高风险回滚前，先复制对应模板再填写。
- 未实际执行的步骤必须明确标记为“未执行”或“待验证”，不要用推测内容补齐。
- 命令、结果、风险、回滚点至少保留一份文本记录；如有截图、日志或工单，可在“附件”中追加链接或路径。
- 模板中的 `<placeholder>` 需要替换成真实值；若某字段不适用，写明“不适用”和原因。

## 必填字段

| 字段 | 要求 |
| --- | --- |
| 时间 | 至少记录开始时间、结束时间，建议使用 UTC |
| 操作者 | 记录执行人、复核人和信息来源 |
| 环境 | 记录目标机、入口地址、目录和环境文件位置 |
| 命令 | 记录实际执行命令，必要时附参数和路径 |
| 结果 | 记录成功/失败/部分完成及关键输出摘要 |
| 风险 | 记录已知风险、偏差、未验证项和后续观察点 |
| 回滚点 | 记录可恢复的快照、备份、旧配置或回退命令 |

## 1. 部署记录模板

```md
# 部署记录

## 文档元信息

- 更新时间：<YYYY-MM-DDTHH:MM:SSZ>
- 记录类型：部署记录
- 执行日期：<YYYY-MM-DD>
- 环境：<staging/production>
- 目标机：<hostname/ip>
- 对外入口：<url>
- 结论：<成功/失败/部分完成>

## 基线信息

- 操作者：<name>
- 复核人：<name-or-n/a>
- 应用目录：<path>
- 环境文件：<path>
- 服务用户：<user>
- 变更来源：<commit/tag/worktree-description>

## 变更目标

- 本次目标：<一句话说明>
- 影响范围：<服务/API/后台/静态资源/cron>
- 前置检查：<已完成项>

## 执行步骤

1. 命令：`<command-1>`
   结果：<成功/失败/摘要>
2. 命令：`<command-2>`
   结果：<成功/失败/摘要>
3. 命令：`<command-3>`
   结果：<成功/失败/摘要>

## 验收结果

- `systemctl status <service>`：<摘要>
- `curl <health/live-or-ready>`：<摘要>
- `curl <public-endpoint>`：<摘要>
- 静态资源 / 图片验证：<摘要>

## 风险与偏差

- 已知风险：<内容>
- 与仓库推荐口径差异：<内容>
- 待补验证项：<内容>

## 回滚点

- 代码回滚点：<commit/tag/path>
- 配置回滚点：<backup-path>
- 数据回滚点：<snapshot/manifest>
- 回滚命令：`<command>`

## 附件

- 日志/截图/工单：<path-or-link>
```

## 2. 恢复演练记录模板

```md
# 恢复演练记录

## 文档元信息

- 更新时间：<YYYY-MM-DDTHH:MM:SSZ>
- 记录类型：恢复演练记录
- 执行日期：<YYYY-MM-DD>
- 环境：<staging/production>
- 目标机：<hostname/ip>
- 快照：<snapshot-path>
- 结论：<成功/失败/部分完成>

## 演练范围

- 操作者：<name>
- 复核人：<name-or-n/a>
- 演练类型：<隔离恢复/原位恢复>
- 恢复目标目录：<path>
- 演练原因：<例行演练/故障复盘/版本验证>

## 执行步骤

1. 备份确认命令：`<command>`
   结果：<摘要>
2. 恢复命令：`<command>`
   结果：<摘要>
3. 服务启动/重启命令：`<command>`
   结果：<摘要>
4. 验证命令：`<command>`
   结果：<摘要>

## 验收结果

- `GET /api/health/deep`：<摘要>
- `make inspect-resources`：<摘要>
- 公开页面/API：<摘要>
- 后台登录/关键后台接口：<摘要>

## 风险与偏差

- 数据一致性风险：<内容>
- 未恢复项：<内容>
- 后续观察点：<内容>

## 回滚点

- 原始快照：<snapshot-path>
- 恢复前保护性备份：<snapshot-path-or-n/a>
- 回滚触发条件：<内容>
- 回滚命令：`<command>`

## 附件

- `restore.log`：<path>
- 恢复记录 JSON：<path>
- 其他日志/截图：<path-or-link>
```

## 3. `cron` 首轮验证记录模板

```md
# cron 首轮验证记录

## 文档元信息

- 更新时间：<YYYY-MM-DDTHH:MM:SSZ>
- 记录类型：cron 首轮验证记录
- 执行日期：<YYYY-MM-DD>
- 目标机：<hostname/ip>
- 环境文件：<path>
- 结论：<成功/失败/部分完成>

## 环境信息

- 操作者：<name>
- 应用目录：<path>
- 日志目录：<path>
- 备份目录：<path>
- `uv` 路径：<path>
- 对外入口：<url-or-n/a>

## 安装与验证步骤

1. 安装命令：`<make install-cron ...>`
   结果：<摘要>
2. `crontab -l`
   结果：<摘要>
3. `create-scheduled-collection-tasks`
   结果：<摘要>
4. `consume-collection-tasks`
   结果：<摘要>
5. `inspect-resources`
   结果：<摘要>
6. `archive-wallpapers`
   结果：<摘要>
7. `backup`
   结果：<摘要>
8. `curl <health/deep>`
   结果：<摘要>

## 关键产物

- `crontab` 备份：<path>
- 日志文件：<paths>
- 备份 `manifest.json`：<path>
- 关键任务统计：<任务数/成功数/失败数>

## 风险与偏差

- 当前与仓库推荐目录差异：<内容>
- 未按调度自然触发的任务：<内容>
- 需要继续观察的项：<内容>

## 回滚点

- 原 `crontab` 备份：<path>
- 回滚命令：`crontab <backup-path>`
- 其他回退说明：<内容>

## 附件

- 目标机日志/截图：<path-or-link>
```

## 4. 域名切换与回滚记录模板

```md
# 域名切换与回滚记录

## 文档元信息

- 更新时间：<YYYY-MM-DDTHH:MM:SSZ>
- 记录类型：域名切换与回滚记录
- 执行日期：<YYYY-MM-DD>
- 原入口：<old-url>
- 新入口：<new-url>
- 结论：<成功/失败/部分完成>

## 变更信息

- 操作者：<name>
- 复核人：<name-or-n/a>
- 变更窗口：<time-range>
- DNS/代理平台：<provider>
- 目标服务：<systemd/nginx/npm/cloud-lb>

## 执行步骤

1. 切换前检查命令：`<command>`
   结果：<摘要>
2. DNS 或代理修改：`<command-or-console-action>`
   结果：<摘要>
3. 入口验证命令：`<command>`
   结果：<摘要>
4. 监控/告警确认：`<command-or-action>`
   结果：<摘要>

## 验收结果

- 首页访问：<摘要>
- 公开 API：<摘要>
- 后台入口：<摘要>
- 图片访问：<摘要>
- TLS / 证书状态：<摘要-or-n/a>

## 风险与偏差

- DNS 生效风险：<内容>
- 缓存/CDN 风险：<内容>
- 外部依赖风险：<内容>

## 回滚点

- 回滚触发条件：<内容>
- 原 DNS/代理配置：<backup-or-screenshot>
- 回滚步骤：<步骤摘要>
- 回滚命令：`<command-or-console-action>`

## 附件

- DNS 截图、代理截图、监控截图：<path-or-link>
```

## 参考样例

- 当前仓库已存在的首个真实样例见 [docs/h4-cron-first-run-record-2026-04-04.md](/home/ops/Projects/BingWall/docs/h4-cron-first-run-record-2026-04-04.md)。
- 后续真实记录建议以“模板文档 + 实际日期文件”的方式沉淀，例如 `docs/deployment-record-2026-04-06.md`。
