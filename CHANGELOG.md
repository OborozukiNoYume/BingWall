# CHANGELOG

## 2026-03-23T00:00:00Z

### 变更内容

- 新增文档总览：[docs/README.md](docs/README.md)
- 新增模块说明：[docs/module-overview.md](docs/module-overview.md)
- 新增数据模型说明：[docs/data-model.md](docs/data-model.md)
- 新增 API 约定：[docs/api-conventions.md](docs/api-conventions.md)
- 新增部署与运行说明：[docs/deployment-runbook.md](docs/deployment-runbook.md)
- 新增阶段 TODO 路线图：[docs/development-roadmap.md](docs/development-roadmap.md)
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
