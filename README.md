# BingWall

## 项目说明

BingWall 是一个围绕 Bing 壁纸构建的图片服务系统。一期目标不是做单一下载脚本，而是建设一个可持续采集、可管理、可对外服务、可扩展演进的内容系统。

当前仓库已进入阶段一代码落地阶段，核心设计以 [系统设计说明书](docs/system-design.md) 为总纲，配套文档用于约束后续实现。

## 当前状态

- 项目阶段：阶段一 `T1.1` 已完成，准备进入 `T1.2`
- 当前代码状态：已完成最小后端工程骨架、统一配置入口、最小 FastAPI 应用和基础测试命令
- 当前文档状态：系统设计、模块说明、数据模型、API 约定、部署运行说明、项目状态与阶段 TODO 已同步到当前实现
- 已确认运行时基线：`Python 3.14.2`、`Node.js 24.13.0`

## 文档入口

- [文档总览](docs/README.md)
- [系统设计说明书](docs/system-design.md)
- [模块说明](docs/module-overview.md)
- [数据模型说明](docs/data-model.md)
- [API 约定](docs/api-conventions.md)
- [部署与运行说明](docs/deployment-runbook.md)
- [阶段 TODO 路线图](docs/TODO.md)
- [项目状态](PROJECT_STATE.md)
- [变更记录](CHANGELOG.md)

## 实施原则

- 以 `docs/system-design.md` 为总纲。
- 一期坚持单机闭环，不引入与当前规模不匹配的复杂基础设施。
- 所有开发任务按“阶段一 / 阶段二 / 阶段三”推进，并以文档中的验收标准作为完成依据。

## 运行说明

当前已确认的一期开发运行时基线如下：

- `Python 3.14.2`
- `Node.js 24.13.0`

当前仓库已提供最小后端启动与验证命令：

```bash
make setup
cp .env.example .env
make verify
make run
```

最小健康检查：

```bash
curl http://127.0.0.1:8000/api/health/live
```

当前 `T1.1` 已补齐内容：

- 后端目录骨架
- `.python-version` 与 `.nvmrc` 运行时版本锁定
- `.env.example` 配置示例与启动期必填校验
- `make setup`、`make verify`、`make run` 统一命令入口
- 最小 FastAPI 服务和 `/api/health/live` 健康检查

当前仍未补齐：

- 数据库初始化命令
- 定时任务触发方式
- 生产环境 `systemd` 与 Nginx 部署脚本
