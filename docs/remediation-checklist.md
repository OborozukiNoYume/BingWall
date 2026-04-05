# BingWall 整改清单

## 文档元信息

- 更新时间：2026-04-05T06:36:49Z
- 来源：`2026-04-04` 项目评估结论
- 文档定位：按优先级输出整改任务、依赖关系与验收命令
- 适用范围：当前一期单机架构仓库与目标部署环境

## 使用说明

- 高优先级：进入试运行前必须完成
- 中优先级：建议在小规模生产稳定前完成
- 低优先级：作为持续改进事项推进
- 每项任务完成后，至少执行本文列出的验收命令，并保留命令输出或截图作为执行记录
- 本文中的 `<your-host>`、`<sample-relative-path>` 等占位符，需要在实际执行时替换为目标环境真实值；`<your-host>` 可以是目标 IP 或正式域名

## 状态总览

- 以下“实际状态”仅基于当前仓库可见文件、当前本地可执行验证，以及本次会话内已完成的离线验收结果整理
- 若某项工作已在真实目标机完成、但未把记录或产物回写到仓库，本表仍会保守标记为“需目标机验证”或“仓库无法确认”

| 编号 | 任务 | 清单标记 | 实际状态 | 说明 |
| --- | --- | --- | --- | --- |
| `H1` | 统一生产监听配置 | `done` | 已完成（仓库） | `systemd`、`nginx`、环境模板、README 与部署文档中的监听口径已对齐 |
| `H2` | 补全生产环境模板 | `done` | 已完成（仓库） | 生产模板已包含 `NASA APOD`、引导管理员和 `OSS` 相关说明 |
| `H3` | 加固 `systemd` 服务沙箱 | `done` | 已完成（仓库） | 当前离线验收基线约为 `2.8`，且 `make verify-deploy` 已通过 |
| `H5` | 完成真实目标机长驻部署与公网接入 | `done` | 已完成（目标机） | 目标机 `139.224.235.228:8000` 已形成长驻服务；本次会话已复核首页、公开 API、样例图片和后台登录入口，对外 `systemd` 状态沿用目标机部署记录 |
| `H4` | 完成首轮 `cron` 闭环验证 | `done` | 已完成（目标机） | 已根据 `2026-04-04` 目标机执行报告回写首轮 `cron` 安装、日志、备份与深度健康检查记录，详见 `docs/h4-cron-first-run-record-2026-04-04.md` |
| `M1` | 正式化 Node 测试链路 | `done` | 已完成（仓库） | `npm test` 已接入 Node 原生测试，`playwright` 已纳入锁文件，浏览器冒烟默认口径已与本地启动脚本对齐 |
| `M2` | 把部署验收纳入自动化 | `done` | 已完成（仓库） | 已保留 `make verify-deploy` 与 runner 统一入口脚本，可在满足前置条件的自托管环境中脚本化执行部署验收；当前仓库不再提供独立 workflow |
| `M3` | 同步项目状态文档 | `done` | 已完成 | `H4` / `H5` 相关口径已同步到 README、部署文档、项目状态、文档索引与变更记录 |
| `M4` | 明确最小告警方案 | `done` | 已完成 | 已在运行手册明确 Webhook 渠道、触发矩阵和值班步骤，并已通过 Server 酱完成 1 次真实测试通知 |
| `M5` | 为关键运维动作补执行记录模板 | `done` | 已完成（仓库） | 已新增固定模板文档，覆盖部署、恢复演练、`cron` 首轮验证、域名切换与回滚场景 |
| `L1` | 拆分超大模块 | `done` | 已完成（仓库） | 已完成后台前端脚本拆分，并把采集主服务与采集仓储改为“门面 + 内部分层”结构；`make verify` 已通过，原 `1k+` 行文件已拆分 |
| `L2` | 建立搜索与查询性能基线 | `done` | 已完成（仓库） | 已新增基准脚本、报告文档与升级阈值记录，当前 `12k` 壁纸样本下无需额外索引或 `FTS` |
| `L3` | 设计密码算法升级路径 | `done` | 已完成（仓库） | 已新增密码哈希升级迁移设计文档，并把现状、渐进迁移和回滚边界同步到相关文档 |
| `L4` | 增加最小运维指标出口 | `done` | 已完成（仓库） | 已新增 `/api/health/metrics`，可读取最近 `7` 天采集成功率、最近备份快照和最近 `24` 小时 HTTP `5xx` 统计 |
| `L5` | 收口前端构建与源码边界 | `done` | 已完成（仓库） | 已补齐前端边界文档、统一构建入口与提交口径，开发者可判断何时重建 CSS、哪些产物必须提交 |

## 高优先级

### H1 统一生产监听配置

- 状态：`done`
- 完成记录：已完成模板、文档与验收脚本同步，参考提交 `dbf29c1`
- 前置依赖：无
- 阻塞后续：`H3`、`H5`、`M2`、`M3`
- 目标：统一 `BINGWALL_APP_HOST` / `BINGWALL_APP_PORT`、`systemd` 模板、`nginx` 模板和部署文档的真实生效口径，避免“环境变量声明”和“服务实际监听地址”不一致
- 交付物：修正后的 [deploy/systemd/bingwall-api.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-api.service)、[deploy/nginx/bingwall.conf](/home/ops/Projects/BingWall/deploy/nginx/bingwall.conf)、[deploy/systemd/bingwall.env.example](/home/ops/Projects/BingWall/deploy/systemd/bingwall.env.example)、[README.md](/home/ops/Projects/BingWall/README.md)、[docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md)
- 验收命令：

```bash
rg -n "BINGWALL_APP_HOST|BINGWALL_APP_PORT|uvicorn|proxy_pass http://127.0.0.1:8000" \
  README.md \
  docs/deployment-runbook.md \
  deploy/systemd/bingwall-api.service \
  deploy/systemd/bingwall.env.example \
  deploy/nginx/bingwall.conf \
  Makefile

make verify-deploy
```

- 通过标准：搜索结果中的监听口径不再互相冲突，且部署验收仍可通过

### H2 补全生产环境模板

- 状态：`done`
- 完成记录：已完成生产环境模板补全与文档说明同步，参考提交 `c30ad23`
- 前置依赖：无
- 阻塞后续：`H4`、`H5`、`M3`
- 目标：把生产部署需要手工补充的关键环境变量显式写入模板，包括 `BINGWALL_COLLECT_NASA_APOD_*`、管理员初始化相关配置和可选项说明
- 交付物：更新后的 [deploy/systemd/bingwall.env.example](/home/ops/Projects/BingWall/deploy/systemd/bingwall.env.example) 与 [docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md)
- 验收命令：

```bash
rg -n "BINGWALL_COLLECT_NASA_APOD_|BINGWALL_SECURITY_BOOTSTRAP_ADMIN_|BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL" \
  .env.example \
  deploy/systemd/bingwall.env.example \
  docs/deployment-runbook.md \
  README.md

make verify-deploy
```

- 通过标准：本地示例与生产模板之间不再存在关键配置缺项，部署文档能解释每个新增键的用途与默认策略

### H3 加固 systemd 服务沙箱

- 状态：`done`
- 完成记录：已完成 `systemd` 服务沙箱加固、部署说明同步与离线验收；移除不必要的附加组后，当前 `systemd-analyze security --offline=yes` 基线约为 `2.8`
- 前置依赖：`H1`
- 阻塞后续：`H5`、`M2`
- 目标：在不破坏当前服务运行的前提下，降低 `systemd-analyze security` 暴露评分，重点收紧能力边界和内核/设备访问权限
- 交付物：更新后的 [deploy/systemd/bingwall-api.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-api.service) 与部署说明中的权限说明
- 验收命令：

```bash
systemd-analyze security /home/ops/Projects/BingWall/deploy/systemd/bingwall-api.service
make verify-deploy
```

- 通过标准：服务可正常启动，部署验收通过，且 `systemd-analyze security` 的整体暴露评分较当前基线明显下降，建议目标小于 `5.0`

### H5 完成真实目标机长驻部署与公网接入

- 状态：`done`
- 完成记录：`2026-04-04` 已在阿里云 Ubuntu 目标机 `139.224.235.228:8000` 完成长期驻留部署；公网入口当前由 `uvicorn` 直接对外监听 `8000/tcp`
- 前置依赖：`H1`、`H2`、`H3`
- 阻塞后续：`H4`、`M4`、`M5`
- 目标：在真实目标机完成 `systemd + 对外访问入口（Nginx Proxy Manager、等价反向代理，或经运维评估后直接开放的公网监听端口） + 域名/目标 IP` 的长期驻留部署，使公开站点、公开 API、图片访问和后台入口可稳定访问；若目标机没有现成反向代理，再退回仓库内的 `Docker nginx` 备用方案
- 交付物：生效中的 [deploy/systemd/bingwall-api.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-api.service) 对应目标机服务、正式环境变量文件，以及真实访问记录；当前已记录的目标机入口为 `http://139.224.235.228:8000`
- 验收命令：

```bash
systemctl status bingwall-api.service --no-pager
curl -I http://139.224.235.228:8000/
curl -sS http://139.224.235.228:8000/api/health/live
curl -sS http://139.224.235.228:8000/api/public/site-info
curl -I http://139.224.235.228:8000/images/bing/2026/04/03_OHR.GrouseGuff_ZH-CN2647001885_preview_1600x900.jpg
curl -I http://139.224.235.228:8000/admin/login
```

- 通过标准：应用服务处于运行态，且经由目标机当前对外入口访问时，首页、公开 API、样例图片和后台登录入口都返回预期状态码

验收记录：

- 目标机部署记录显示 `bingwall-api.service` 已处于 `active` 且 `enabled` 状态；该项为目标机执行记录，当前会话未直接登录目标机复核
- 本次会话已外部复核 `http://139.224.235.228:8000/`、`/api/health/live`、`/api/public/site-info`、`/images/bing/2026/04/03_OHR.GrouseGuff_ZH-CN2647001885_preview_1600x900.jpg` 与 `/admin/login`，均返回预期 `200` 或有效 JSON
- 当前公网响应头显示 `server: uvicorn`，说明这台已验收目标机当前采用“应用直接监听公网 `8000/tcp`”的最小入口，而非额外代理层

补充说明：

- 仓库仍推荐优先复用现成的 Nginx Proxy Manager 或等价反向代理；当前目标机之所以可直接按 `http://139.224.235.228:8000` 验收，是因为运维侧已经显式开放公网 `8000/tcp`
- 若后续需要把当前已验收目标机收敛回仓库推荐口径，可再把应用监听改回 `127.0.0.1:8000`，并在外层补一层现成代理配置
- 若真实目标机没有现成反向代理，可选用 [deploy/systemd/bingwall-nginx.service](/home/ops/Projects/BingWall/deploy/systemd/bingwall-nginx.service) + [deploy/nginx/bingwall.conf](/home/ops/Projects/BingWall/deploy/nginx/bingwall.conf) 作为备用方案

### H4 完成首轮 cron 闭环验证

- 状态：`done`
- 完成记录：已根据 `2026-04-04` 目标机执行报告回写首轮闭环记录，见 [docs/h4-cron-first-run-record-2026-04-04.md](/home/ops/Projects/BingWall/docs/h4-cron-first-run-record-2026-04-04.md)
- 前置依赖：`H2`、`H5`
- 阻塞后续：`M4`、`M5`
- 目标：在目标机完成 `cron` 安装并确认“建任务、消费队列、巡检、归档、备份”至少成功跑完 1 轮
- 交付物：已安装的 `crontab`、首轮运行日志、样例备份产物、首轮深度健康检查记录，以及 [docs/h4-cron-first-run-record-2026-04-04.md](/home/ops/Projects/BingWall/docs/h4-cron-first-run-record-2026-04-04.md)
- 验收命令：

```bash
make install-cron \
  CRON_APP_DIR=/home/ubuntu/BingWall \
  CRON_ENV_FILE=/etc/bingwall/bingwall.env \
  CRON_LOG_DIR=/var/log/bingwall \
  CRON_UV_BIN=/home/ubuntu/.local/bin/uv
crontab -l | rg "create-scheduled-collection-tasks|consume-collection-tasks|inspect-resources|archive-wallpapers|backup"
find /var/log/bingwall -maxdepth 1 -type f | sort
find /home/ubuntu/BingWall/var/backups -maxdepth 2 -name manifest.json | sort
curl -sS http://127.0.0.1:8000/api/health/deep
```

- 通过标准：计划任务已安装，且已在目标机手工验证“建任务、消费队列、巡检、归档、备份”5 类任务至少成功跑完 1 轮；日志目录和备份目录都有首轮产物，深度健康检查返回可解释的正常结果

验收记录：

- 以下记录基于 `2026-04-04` 的目标机执行报告回写到仓库；当前会话未直接登录目标机复核
- 目标机已执行 `make install-cron`，并把 5 条 `cron` 任务安装到当前用户 `crontab`；安装前旧 `crontab` 已备份到 `/var/log/bingwall/crontab.backup.20260404T091149Z.txt`
- `create-scheduled-collection-tasks` 首轮手工验证成功创建 `9` 个任务，其中 `8` 个 Bing 市场任务、`1` 个 `NASA APOD` 任务
- `consume-collection-tasks --max-tasks 5` 首轮手工验证成功处理 `5` 个任务，累计成功下载 `9` 张图片
- `run_resource_inspection.py` 已巡检 `20` 个资源，未发现缺失或损坏；`run_wallpaper_archive.py` 已成功执行，当前新部署环境无历史资源需要归档
- `run_backup.py --skip-nginx --skip-tmpfiles` 已产出 `var/backups/backup-20260404T094004Z-d0172fd9/manifest.json`，深度健康检查 `http://127.0.0.1:8000/api/health/deep` 返回 `healthy`

补充说明：

- 当前已验收目标机采用 `ubuntu` 用户在 `/home/ubuntu/BingWall` 直接部署，目录口径与仓库推荐的 `/opt/bingwall/app` / `bingwall` 用户方案存在差异
- 当前目标机未额外部署反向代理，公网入口仍为 `http://139.224.235.228:8000`
- 备份任务之所以使用 `--skip-nginx --skip-tmpfiles`，是因为该目标机当前不存在仓库推荐口径下的本地 `nginx` 与 `tmpfiles` 配置文件

## 中优先级

### M1 正式化 Node 测试链路

- 状态：`done`
- 完成记录：已补充 `tests/node/*.test.js`、正式纳入 `playwright` 开发依赖，并把 `scripts/dev/run-api.sh` 与浏览器冒烟默认配置统一到本地 `.env` 口径
- 前置依赖：无
- 阻塞后续：`L5`
- 目标：让 `npm test` 不再是占位脚本，并把浏览器冒烟依赖纳入可复现安装流程
- 交付物：更新后的 [package.json](/home/ops/Projects/BingWall/package.json)、[package-lock.json](/home/ops/Projects/BingWall/package-lock.json)、Node 测试文件、浏览器冒烟配置脚本与前端验证说明
- 验收命令：

```bash
npm ci
npm test

# 另开一个终端启动本地服务
bash scripts/dev/run-api.sh

# 再执行浏览器冒烟
make browser-smoke
```

- 通过标准：`npm ci` 后无需再手工 `npm install --no-save playwright`，且 `npm test` 与浏览器冒烟都能直接跑通

### M2 把部署验收纳入自动化

- 状态：`done`
- 完成记录：已保留 [scripts/github/run_verify_deploy.sh](/home/ops/Projects/BingWall/scripts/github/run_verify_deploy.sh) 与仓库内 `make verify-deploy` 统一入口，便于在满足 `systemd --user`、Docker 与 `uv` 前置条件的自托管环境中脚本化执行部署验收；当前仓库不再提供独立 `verify-deploy.yml` workflow
- 前置依赖：`H1`、`H3`
- 阻塞后续：无
- 目标：把 [scripts/verify_t1_6.py](/home/ops/Projects/BingWall/scripts/verify_t1_6.py) 或等价部署验收沉淀为可复用的脚本化入口，避免部署模板回归只靠人工临时拼装命令发现
- 交付物：runner 统一入口脚本、仓库内执行口径与部署验收命令说明
- 验收命令：

```bash
rg -n "verify_t1_6.py|make verify-deploy" \
  scripts/github/run_verify_deploy.sh \
  README.md \
  docs/deployment-runbook.md

# 若当前环境满足 systemd --user、Docker 与 uv 前置条件，可直接执行
bash scripts/github/run_verify_deploy.sh
```

- 通过标准：仓库内存在可复用的脚本化入口，且可在满足前置条件的自托管环境中执行部署验收

### M3 同步项目状态文档

- 状态：`done`
- 完成记录：已基于 `2026-04-04` 的 `H4` / `H5` 目标机执行记录同步 [README.md](/home/ops/Projects/BingWall/README.md)、[PROJECT_STATE.md](/home/ops/Projects/BingWall/PROJECT_STATE.md)、[docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md)、[docs/README.md](/home/ops/Projects/BingWall/docs/README.md) 与 [CHANGELOG.md](/home/ops/Projects/BingWall/CHANGELOG.md)
- 前置依赖：`H1`、`H2`、`H4`、`H5`
- 阻塞后续：无
- 目标：统一 README、项目状态、部署文档和变更记录里对阶段状态、未完成项和当前运维缺口的描述
- 交付物：更新后的 [README.md](/home/ops/Projects/BingWall/README.md)、[PROJECT_STATE.md](/home/ops/Projects/BingWall/PROJECT_STATE.md)、[docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md)、[docs/README.md](/home/ops/Projects/BingWall/docs/README.md) 与 [CHANGELOG.md](/home/ops/Projects/BingWall/CHANGELOG.md)
- 验收命令：

```bash
rg -n "阶段三|cron|监听地址|NASA APOD|公网|试运行" \
  README.md \
  PROJECT_STATE.md \
  docs/deployment-runbook.md \
  CHANGELOG.md
```

- 通过标准：同一事项在不同文档中的状态描述保持一致，不再出现互相冲突的阶段口径

### M4 明确最小告警方案

- 状态：`done`
- 完成记录：已在 [docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md) 补充“最小告警方案（M4）”章节，明确当前阶段采用“运维值班群 Webhook + 外层巡检/监控”的最小落地口径，并给出触发矩阵、检查命令和值班处理步骤；另已于 `2026-04-05T03:22:59Z` 使用 Server 酱完成 1 次真实测试通知，推送入队返回 `code = 0`，状态查询 `wxstatus` 返回成功
- 前置依赖：`H4`、`H5`
- 阻塞后续：`L4`
- 目标：确定最小可落地的告警渠道和触发矩阵，至少覆盖采集连续失败、深度健康异常、备份过期和磁盘占用过高
- 交付物：告警渠道决策、触发矩阵、值班处理步骤，建议沉淀到 [docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md)
- 验收命令：

```bash
rg -n "告警|Webhook|邮件|触发条件|值班|升级路径" docs/deployment-runbook.md docs/remediation-checklist.md

# 若最终采用 Webhook，可执行一次测试通知
curl -sS -X POST "<webhook-url>" \
  -H "Content-Type: application/json" \
  -d '{"text":"bingwall alert test"}'
```

- 通过标准：已有明确告警渠道与触发条件，且至少完成 1 次真实测试通知

补充说明：

- 仓库内不保存真实 SENDKEY；如后续轮换密钥或切换到其他值班群，应只更新运维记录与受控环境配置

### M5 为关键运维动作补执行记录模板

- 状态：`done`
- 完成记录：已新增 [docs/operations-record-templates.md](/home/ops/Projects/BingWall/docs/operations-record-templates.md)，并在 [docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md) 中补充模板使用入口与记录要求
- 前置依赖：`H4`、`H5`
- 阻塞后续：无
- 目标：为部署、恢复演练、cron 首轮验证、域名切换等关键动作建立固定记录模板，降低后续交接和复盘成本
- 交付物：执行记录模板文档 [docs/operations-record-templates.md](/home/ops/Projects/BingWall/docs/operations-record-templates.md)，以及 [docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md) 中的使用说明
- 验收命令：

```bash
rg -n "执行记录|部署记录|恢复演练记录|cron 首轮验证记录|回滚记录" docs
```

- 通过标准：仓库中能找到可复用的记录模板，且字段覆盖时间、操作者、命令、结果、风险和回滚点

## 低优先级

### L1 拆分超大模块

- 状态：`done`
- 完成记录：已完成 `web/admin/assets/admin.js` 拆分，并于 `2026-04-05` 继续完成 `app/services/source_collection.py`、`app/repositories/collection_repository.py` 的内部分层；当前分别改为“兼容门面 + 采集编排 / 资源流水线 / 工具模块”和“兼容门面 + 任务 / 壁纸 / 资源 mixin”结构
- 前置依赖：建议在高优先级完成后执行
- 阻塞后续：无
- 目标：降低大文件维护成本，优先拆分采集主服务、公开仓储查询和后台前端脚本
- 交付物：拆分后的模块结构、补齐的测试和必要文档更新；当前已新增 `web/admin/assets/pages/*.js`、`web/admin/assets/modules/core.js`
- 验收命令：

```bash
make verify
find app/services app/repositories web/admin/assets -type f | xargs wc -l | sort -n | tail -n 20
```

- 通过标准：行为不变，验证通过，且极端大文件数量较当前明显减少

补充说明：

- 本轮已优先完成后台前端脚本拆分，并同步更新 Tailwind 扫描源、前端集成测试和 README / 项目状态文档
- 本轮完成后，原 `app/services/source_collection.py`（`1294` 行）与 `app/repositories/collection_repository.py`（`1057` 行）已拆分为多个职责模块；当前最大单文件已降到约 `700` 行量级，`make verify` 于 `2026-04-05` 复验通过

### L2 建立搜索与查询性能基线

- 状态：`done`
- 完成记录：已新增 [scripts/benchmark_public_queries.py](/home/ops/Projects/BingWall/scripts/benchmark_public_queries.py) 与 [docs/benchmark-report.md](/home/ops/Projects/BingWall/docs/benchmark-report.md)，形成公开列表 / 后台内容列表的离线可复跑基准
- 前置依赖：无
- 阻塞后续：无
- 目标：针对公开列表和后台内容列表的关键词、标签、日期过滤建立可重复的性能基线，并定义何时需要额外索引或 FTS
- 交付物：性能基准脚本、样本数据规模说明、报告文档
- 验收命令：

```bash
# 以下命令依赖本任务新增的基准脚本与报告
uv run python scripts/benchmark_public_queries.py
rg -n "P50|P95|P99|升级阈值|FTS" docs/benchmark-report.md
```

- 通过标准：有可复跑的基准命令，有明确数据规模和升级阈值，不再只靠经验判断

补充说明：

- 本轮基线默认造数 `12,000` 条壁纸、`24,000` 条本地化、`24,000` 条图片资源和 `36,000` 条标签绑定
- `2026-04-05T05:47:44Z` 实测结果显示：公开关键词检索 `P95 = 24.2ms`、后台关键词检索 `P95 = 25.4ms`，当前仍明显低于阈值
- 当前升级口径已写入 [docs/benchmark-report.md](/home/ops/Projects/BingWall/docs/benchmark-report.md)：纯日期类查询先看常规索引，关键词场景超阈值或数据量接近 `50,000` 行时再评估 `SQLite FTS`

### L3 设计密码算法升级路径

- 状态：`done`
- 完成记录：已新增 [docs/password-hash-migration.md](/home/ops/Projects/BingWall/docs/password-hash-migration.md)，并把部署文档与系统设计中的密码算法现状说明补充到统一迁移设计入口
- 前置依赖：无
- 阻塞后续：无
- 目标：在不破坏现有登录链路的前提下，形成从 `pbkdf2_sha256` 向更强算法迁移的兼容设计
- 交付物：迁移设计文档与兼容策略说明，见 [docs/password-hash-migration.md](/home/ops/Projects/BingWall/docs/password-hash-migration.md)
- 验收命令：

```bash
rg -n "argon2id|pbkdf2_sha256|兼容验证|渐进迁移|回滚方案" docs
```

- 通过标准：文档中明确记录哈希兼容读取、渐进重哈希与回滚策略

### L4 增加最小运维指标出口

- 状态：`done`
- 完成记录：已新增 [app/repositories/migrations/versions/V0010__http_request_5xx_events.sql](/home/ops/Projects/BingWall/app/repositories/migrations/versions/V0010__http_request_5xx_events.sql)、[app/api/health.py](/home/ops/Projects/BingWall/app/api/health.py) 中的 `/api/health/metrics` 接口，并把 README / 部署手册同步到统一读取口径；`uv run pytest tests/integration/test_health_checks.py` 已通过
- 前置依赖：`M4`
- 阻塞后续：无
- 目标：让运维能够快速回答“最近采集成功率、最近备份时间、最近 5xx 情况”等基础问题
- 交付物：最小指标导出方案、说明文档，以及对应接口；当前统一入口为 [app/api/health.py](/home/ops/Projects/BingWall/app/api/health.py) 中的 `GET /api/health/metrics`
- 验收命令：

```bash
rg -n "采集成功率|最近备份时间|5xx|指标出口|/api/health/metrics" docs README.md
curl -sS http://127.0.0.1:30003/api/health/metrics
uv run pytest tests/integration/test_health_checks.py
```

- 通过标准：关键运维指标可以被稳定读取，且读取方式已写入文档

### L5 收口前端构建与源码边界

- 状态：`done`
- 完成记录：已新增 [docs/frontend-build-boundary.md](/home/ops/Projects/BingWall/docs/frontend-build-boundary.md)，并补充 `make frontend-build` / `make frontend-watch` 与 `npm run build:css` / `npm run watch:css` 统一入口；README、部署文档和文档索引已同步前端源码 / 构建产物边界
- 前置依赖：`M1`
- 阻塞后续：无
- 目标：明确 `web/src`、`web/public/assets`、`web/admin/assets` 的职责，避免构建产物和手工维护文件混用
- 交付物：前端边界说明文档、统一构建命令与更新后的前端构建说明；当前以 [docs/frontend-build-boundary.md](/home/ops/Projects/BingWall/docs/frontend-build-boundary.md)、[README.md](/home/ops/Projects/BingWall/README.md)、[docs/deployment-runbook.md](/home/ops/Projects/BingWall/docs/deployment-runbook.md)、[docs/README.md](/home/ops/Projects/BingWall/docs/README.md)、[package.json](/home/ops/Projects/BingWall/package.json) 与 [Makefile](/home/ops/Projects/BingWall/Makefile) 为准
- 验收命令：

```bash
rg -n "web/src|web/public/assets|web/admin/assets|构建产物|源码" \
  README.md \
  docs/README.md \
  docs/remediation-checklist.md \
  package.json \
  Makefile
```

- 通过标准：开发者可以明确判断“改哪个目录、是否需要重新构建、构建产物是否应提交”
