# BingWall 密码哈希升级迁移设计

## 文档元信息

- 更新时间：2026-04-05T05:59:39Z
- 文档定位：为后台管理员密码从 `pbkdf2_sha256` 渐进迁移到更强算法提供兼容设计、验证要求与回滚边界
- 当前实现基线：`app/core/security.py`、`app/services/admin_auth.py`、`app/services/admin_bootstrap.py`

## 背景与现状

当前仓库里的管理员密码哈希路径如下：

- `app/core/security.py` 只支持 `pbkdf2_sha256`
- 哈希格式固定为 `pbkdf2_sha256$<iterations>$<salt>$<digest>`
- 当前写入入口只有两处：初始化管理员 `app/services/admin_bootstrap.py` 和后台改密 `app/services/admin_auth.py`
- 当前读取入口主要为登录校验和改密前的当前密码校验，都会调用 `verify_password`
- `admin_users.password_hash` 已是 `TEXT`，现阶段不需要为算法升级新增字段或变更 schema

当前安全边界：

- `pbkdf2_sha256` 迭代次数固定为 `600000`
- 当前代码无法识别第二种密码算法
- 一旦直接把写入算法切到 `argon2id`，旧版代码将无法验证新哈希，存在登录中断风险

因此，`L3` 的目标不是立刻切换算法，而是先把“兼容读取、渐进迁移、可回滚”三件事设计清楚。

## 目标

- 在不破坏现有登录链路的前提下，为 `pbkdf2_sha256 -> argon2id` 提供兼容迁移路径
- 保持 `admin_users.password_hash` 单字段存储，不引入额外密码表
- 让新写入密码最终统一收敛到 `argon2id`
- 允许迁移期间同时验证历史 `pbkdf2_sha256` 和新 `argon2id`

## 非目标

- 本文不声明仓库当前已经支持 `argon2id`
- 本文不要求本轮立即引入第三方密码库或上线真实参数
- 本文不扩展密码复杂度策略；复杂度仍沿用当前“最少 `12` 位”的现有口径

## 目标口径

建议把目标算法收敛为 `argon2id`，并使用标准 PHC 风格字符串作为最终存储格式，例如：

```text
argon2id$v=19$m=<memory_cost>,t=<time_cost>,p=<parallelism>$<salt>$<digest>
```

说明：

- `pbkdf2_sha256` 继续保留当前自定义四段格式，用于兼容历史数据
- `argon2id` 建议直接使用业界通用的自描述格式，避免再次自定义私有编码
- 具体参数值应在真正实现时结合目标机 CPU / 内存预算压测后定版；本文只先固定“算法与格式方向”

## 兼容验证设计

建议把密码校验从“单算法硬编码”改为“按前缀分发”：

1. 读取 `password_hash`
2. 根据前缀识别算法
3. 分别调用对应验证器
4. 返回“是否通过”与“是否需要重哈希”两个结果

建议新增的内部抽象：

- `identify_password_hash_algorithm(password_hash: str) -> str | None`
- `verify_password(password: str, password_hash: str) -> bool`
- `password_hash_needs_rehash(password_hash: str) -> bool`
- `hash_password(password: str) -> str`

建议行为：

- `verify_password` 负责兼容读取 `pbkdf2_sha256` 与 `argon2id`
- `hash_password` 只负责当前写入主算法；切换后统一输出 `argon2id`
- `password_hash_needs_rehash` 用于判断“验证通过但仍是旧算法”或“参数已落后”

兼容读取规则：

- 前缀为 `pbkdf2_sha256$`：走现有 `pbkdf2_hmac("sha256", ...)`
- 前缀为 `argon2id$`：走 `argon2id` 验证器
- 前缀未知或格式损坏：直接返回失败，不尝试猜测

## 渐进迁移设计

推荐采用“双读、单写、登录后渐进重哈希”：

### 阶段 0：设计与测试准备

- 保持当前写入算法仍为 `pbkdf2_sha256`
- 先补齐多算法单元测试和登录链路集成测试
- 确认 `admin_users.password_hash` 现有数据都能被前缀识别

### 阶段 1：引入双读能力

- 在 `app/core/security.py` 中增加 `argon2id` 识别与验证
- 此阶段写入口仍保持 `pbkdf2_sha256`
- 目标是先确保新版本对“旧哈希”和“未来新哈希”都可读

### 阶段 2：切换单写口径

- 把 `hash_password` 的输出切换到 `argon2id`
- `app/services/admin_bootstrap.py` 创建的首个管理员改为写入 `argon2id`
- `app/services/admin_auth.py` 改密成功后写入 `argon2id`

### 阶段 3：登录成功后渐进重哈希

- 当用户使用旧 `pbkdf2_sha256` 哈希成功登录后，立即在同一请求内重写为 `argon2id`
- 只在“密码验证通过”后执行重哈希，不做离线批量猜测式迁移
- 建议保留审计日志，例如记录一次 `admin_password_rehashed` 或等价安全事件

### 阶段 4：稳定观察

- 通过查询统计剩余 `pbkdf2_sha256$%` 的账号数量
- 当剩余量接近 `0` 且经历一个可接受观察窗口后，再决定是否移除旧算法写入逻辑
- 旧算法读取逻辑不应过早删除；至少应跨过一次完整发布回滚窗口

## 代码落点建议

建议改动边界如下：

- `app/core/security.py`
  - 增加算法识别、`argon2id` 校验、是否需要重哈希判断
- `app/services/admin_auth.py`
  - 登录成功后，如果检测到旧哈希则执行渐进重哈希
  - 改密继续走统一 `hash_password`
- `app/services/admin_bootstrap.py`
  - 初始化管理员写入当前主算法
- `tests/unit/test_security.py`
  - 增加 `pbkdf2_sha256`、`argon2id`、损坏格式、未知前缀、需要重哈希判定等测试
- `tests/integration/test_admin_auth.py`
  - 增加“旧哈希登录成功后被升级”“新哈希仍可登录”“回滚窗口内双读有效”等测试

数据库与迁移要求：

- `admin_users.password_hash` 继续复用现有 `TEXT`
- 本方案默认不新增 SQLite migration
- 如未来需要额外审计字段，应作为独立任务评估，不并入本次算法升级

## 验证计划

实现时至少覆盖以下兼容验证：

| 场景 | 预期 |
| --- | --- |
| 旧 `pbkdf2_sha256` 哈希登录 | 登录成功 |
| 旧 `pbkdf2_sha256` 哈希登录后渐进迁移 | 数据库哈希改写为 `argon2id` |
| `argon2id` 哈希登录 | 登录成功 |
| 改密 | 新密码以 `argon2id` 写入 |
| 初始化管理员 | 新建账号以 `argon2id` 写入 |
| 损坏哈希 / 未知前缀 | 登录失败，不抛出未处理异常 |
| 回滚版本保留双读 | 已迁移账号仍可登录 |

建议验收命令：

```bash
uv run -m pytest tests/unit/test_security.py tests/integration/test_admin_auth.py -q
sqlite3 <db-path> "SELECT COUNT(*) FROM admin_users WHERE password_hash LIKE 'pbkdf2_sha256$%';"
sqlite3 <db-path> "SELECT COUNT(*) FROM admin_users WHERE password_hash LIKE 'argon2id$%';"
```

## 上线步骤建议

1. 先发布“支持双读、仍写 `pbkdf2_sha256`”版本
2. 完成兼容验证后，再发布“切到 `argon2id` 单写”版本
3. 观察登录链路和错误日志
4. 确认稳定后，启用“登录成功后渐进重哈希”

这样拆分的原因：

- 可把“能否识别新算法”和“是否开始写入新算法”分成两个发布面
- 出现问题时更容易定位是读路径问题还是写路径问题
- 能避免首个发布就同时承担依赖引入、写入切换和数据迁移三类风险

## 回滚方案

回滚原则：任何回滚版本都必须保留对 `argon2id` 的读取能力。

原因：

- 一旦某些账号已被重哈希为 `argon2id`，纯旧版 `pbkdf2_sha256` 代码将无法登录
- 因此“代码回滚到不支持 `argon2id` 的历史版本”不是安全回滚，只能算破坏性回退

推荐回滚路径：

1. 若问题发生在“阶段 1 双读引入”期间：直接回滚到上一版通常安全，因为此时数据库里还没有 `argon2id` 新写入
2. 若问题发生在“阶段 2/3 已开始写入或渐进迁移”之后：只能回滚到“仍保留双读能力、但停用新写入 / 停用重哈希”的修复版本
3. 若必须回到完全旧版：需要先恢复数据库备份，或确认所有账号仍保留 `pbkdf2_sha256`，否则会导致部分管理员无法登录

回滚开关建议：

- 开关 A：是否允许 `hash_password` 写入 `argon2id`
- 开关 B：登录成功后是否执行渐进重哈希

最低安全要求：

- 即使关闭开关 A/B，也不能去掉 `argon2id` 的兼容验证

## 风险与约束

- `argon2id` 对 CPU / 内存更敏感，参数过大可能拉高登录延迟
- 当前仓库使用同步 SQLite 仓储；若登录时顺带执行重哈希，需注意单请求耗时
- 若未来要做多管理员批量导入，应继续复用统一哈希入口，避免绕过主算法
- 若后续要强化密码复杂度，应单独作为策略任务推进，不要和算法迁移捆绑上线

## 当前结论

- `L3` 当前可先视为“设计完成”，不应把文档任务误判为已完成代码切换
- 推荐的实施顺序是：先双读，再单写，最后渐进迁移
- 在真正落地前，必须先补齐 `tests/unit/test_security.py` 与 `tests/integration/test_admin_auth.py` 的兼容验证
