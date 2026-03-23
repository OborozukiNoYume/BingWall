# CHANGELOG

## 2026-03-23T13:33:04Z

### 变更内容

- 更新 [README.md](README.md)，同步当前阶段状态，并补充已确认的一期开发运行时基线 `Python 3.14.2`、`Node.js 24.13.0`
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md)，将项目状态调整为阶段一 `T1.1` 前置准备阶段，并记录已确认的开发运行时基线
- 更新 [docs/deployment-runbook.md](docs/deployment-runbook.md)，将目标环境中的 `Python` 与 `Node.js` 运行时版本改为明确记录，补充“已确认基线但尚未生成锁定文件”的说明

### 变更原因

- 根据当前机器已确认可用的开发环境，先固定一期实现所使用的运行时基线
- 关闭“运行时版本尚未确定”的文档缺口，为后续阶段一代码初始化提供统一依据

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖安装
- 不涉及运行时行为变更

### 验证步骤

- 确认 [README.md](README.md) 已记录 `Python 3.14.2` 和 `Node.js 24.13.0`
- 确认 [PROJECT_STATE.md](PROJECT_STATE.md) 中“当前阶段”“当前技术路线”“未完成内容”与运行时基线表述一致
- 确认 [docs/deployment-runbook.md](docs/deployment-runbook.md) 的目标环境表已记录精确运行时版本，且未误写为“已存在锁定文件”

### 回滚说明

- 如需回滚本次变更，可恢复 [README.md](README.md)、[PROJECT_STATE.md](PROJECT_STATE.md)、[docs/deployment-runbook.md](docs/deployment-runbook.md) 与 [CHANGELOG.md](CHANGELOG.md) 的上一版本
- 本次变更仅影响文档说明，不影响现有代码、依赖或数据

## 2026-03-23T13:18:49Z

### 变更内容

- 更新 [docs/TODO.md](docs/TODO.md)，为 `T1.1` 到 `T3.6` 的既有 TODO 补充可勾选子任务 Checklist

### 变更原因

- 将已有阶段路线图细化为可直接执行和勾选的开发子任务
- 让每条 TODO 与现有模块说明、数据模型、API 约定和部署约束形成更明确的落地路径

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认 `docs/TODO.md` 中每个现有 TODO 均新增且仅新增一个“子任务”段落
- 确认未修改 TODO 编号、阶段归属、`depends_on`、验收标准、`source_design` 和 `source_spec`
- 确认每条子任务均使用动词开头，且包含核心业务实现与测试或验证动作

### 回滚说明

- 如需回滚本次变更，可恢复本次修改前的 `docs/TODO.md` 与 `CHANGELOG.md`
- 本次变更仅影响文档说明，不影响现有代码或数据

## 2026-03-23T12:57:44Z

### 变更内容

- 更新 [docs/TODO.md](docs/TODO.md)，修正 `T2.4`、`T3.4` 依赖与验收口径，并补充采集重试、恢复验证、搜索响应时间要求
- 更新 [docs/data-model.md](docs/data-model.md)，补齐 `admin_sessions`、`tags`、`wallpaper_tags`、`download_events` 数据结构，并明确 `resource_status` 与 `image_status` 的同步责任
- 更新 [docs/api-conventions.md](docs/api-conventions.md)，补充后台登出接口、标签与下载登记扩展接口，并澄清后台日志查询与结构化任务日志的关系
- 更新 [docs/module-overview.md](docs/module-overview.md) 与 [docs/system-design.md](docs/system-design.md)，明确调度模块只负责触发，补充 API 路由前缀和运维告警基线
- 更新 [docs/deployment-runbook.md](docs/deployment-runbook.md)，补齐会话密钥、密码策略和默认告警阈值要求
- 更新 [PROJECT_STATE.md](PROJECT_STATE.md)，同步最新文档决策与开放问题

### 变更原因

- 修正文档中已确认的依赖链和职责边界不一致
- 补齐阶段二和阶段三路线图已承诺但尚未落到数据模型或 API 契约的内容
- 让状态联动、会话管理和运维配置要求具备更明确的执行口径

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认 `docs/TODO.md` 的依赖拓扑与 `depends_on` 字段不再互相冲突
- 确认标签、会话和下载登记在 TODO、数据模型、API 约定之间均有对应落点
- 确认公开可见规则统一为 `content_status`、`is_public`、`image_status` 与 `resource_status` 联合约束
- 确认调度模块与采集模块的职责边界在模块说明和系统设计中一致
- 确认部署文档中的安全与告警基线已给出可执行的默认值

### 回滚说明

- 如需回滚本次变更，可恢复本次修改前的相关文档版本
- 本次变更仅影响文档说明，不影响现有代码或数据

## 2026-03-23T12:30:47Z

### 变更内容

- 更新 [docs/system-design.md](docs/system-design.md)，统一公开筛选与公开可见规则
- 更新 [docs/data-model.md](docs/data-model.md)，明确 `image_status` 与 `resource_status` 的关系，并补充下载可见性规则
- 更新 [docs/api-conventions.md](docs/api-conventions.md)，澄清统一响应结构示例语义，并补齐站点信息、后台详情、日志和审计接口契约
- 更新 [docs/deployment-runbook.md](docs/deployment-runbook.md)，区分阶段一公开链路最小检查与阶段二完整上线检查
- 更新 [docs/TODO.md](docs/TODO.md)，同步调整 API、部署和验收口径
- 更新 [docs/README.md](docs/README.md)，同步 TODO 文档定位

### 变更原因

- 修正文档间公开筛选规则冲突
- 补齐设计总纲已要求但 API 契约缺失的接口
- 让部署检查与阶段路线图保持一致
- 让 TODO 的验收标准与最新文档口径一致

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认公开可见规则在系统设计、数据模型、API 契约和 TODO 中一致
- 确认 API 文档中的示例已明确为 `data` 字段结构
- 确认后台详情、任务详情、日志和审计接口在 API 文档中已有定义
- 确认部署文档的阶段一和阶段二检查项与 TODO 阶段边界一致

### 回滚说明

- 如需回滚本次变更，可恢复本次修改前的相关文档版本
- 本次变更仅影响文档说明，不影响现有代码或数据

## 2026-03-23T12:11:15Z

### 变更内容

- 更新 [docs/TODO.md](docs/TODO.md)
- 对阶段 TODO 做系统级校准，补充依赖拓扑、来源标注、输入输出和状态字段
- 合并重复或过细任务：`TODO-3 + TODO-4`、`TODO-10 + TODO-11`
- 强化每条 TODO 的验收标准和可观测性要求

### 变更原因

- 让路线图与系统设计总纲及专项文档保持一致
- 修正任务依赖，避免后台绕过 API、部署顺序失真和任务粒度不一致
- 让后续实施时可以直接按任务来源、输入输出和验收条件执行

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认每条 TODO 都标注了 `source_design` 和 `source_spec`
- 确认所有任务均带有 `depends_on`、`输入`、`输出`、`验收标准` 和 `status`
- 确认不存在循环依赖和跨阶段反向依赖
- 确认每阶段任务数均不超过 8

### 回滚说明

- 如需回滚本次变更，可恢复上一版 `docs/TODO.md`
- 本次变更仅影响路线图结构，不影响已有设计总纲和其他文档边界

## 2026-03-23T00:00:00Z

### 变更内容

- 新增文档总览：[docs/README.md](docs/README.md)
- 新增模块说明：[docs/module-overview.md](docs/module-overview.md)
- 新增数据模型说明：[docs/data-model.md](docs/data-model.md)
- 新增 API 约定：[docs/api-conventions.md](docs/api-conventions.md)
- 新增部署与运行说明：[docs/deployment-runbook.md](docs/deployment-runbook.md)
- 新增阶段 TODO 路线图：[docs/TODO.md](docs/TODO.md)
- 新增项目状态文件：`PROJECT_STATE.md`
- 更新 `README.md`，补充项目说明和文档入口

### 变更原因

- 以 `docs/system-design.md` 为总纲，补齐实施前缺失的配套文档
- 让后续开发、验收、部署和协作有统一依据
- 将阶段目标拆成可执行 TODO，降低后续实施歧义

### 影响范围

- 影响范围仅限文档层
- 不涉及代码实现
- 不涉及依赖变更
- 不涉及运行时行为变更

### 验证步骤

- 确认 `README.md` 已能作为项目入口定位所有核心文档
- 确认 `docs/` 下已有模块说明、数据模型、API 约定、部署说明和路线图
- 确认路线图中的每条 TODO 都包含依赖关系和验收标准
- 确认文档之间技术路线保持一致，均以单机一期方案为前提

### 回滚说明

- 如需回滚本次变更，可删除新增文档并恢复 `README.md`
- 本次变更仅涉及文档，不影响运行环境和数据文件
