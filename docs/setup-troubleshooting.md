# 环境搭建问题排查记录

> 记录时间：2026-03-27
> 环境：Python 3.14.2, Ubuntu Linux

## 问题 1：pip 安装指定版本时找不到包

### 现象
```bash
pip install fastapi==0.116.1
# ERROR: No matching distribution found for fastapi==0.116.1
```

### 原因
网络超时导致 pip 无法正确查询 PyPI 索引，返回错误的"找不到包"信息。

### 解决方案
1. 先不指定版本安装，让 pip 自动选择兼容版本：
   ```bash
   .venv/bin/pip install fastapi
   ```
2. 或重试多次，等待网络恢复

---

## 问题 2：Pillow 指定版本安装失败

### 现象
```bash
pip install Pillow==12.1.1
# ERROR: Could not find a version that satisfies the requirement Pillow==12.1.1
```

### 原因
同上，网络问题导致索引查询失败。

### 解决方案
不指定版本直接安装：
```bash
.venv/bin/pip install Pillow
# Successfully installed Pillow-12.1.1
```

---

## 问题 3：环境变量验证失败

### 现象
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
storage_oss_public_base_url
  Input should be a valid URL, input is empty
```

### 原因
`.env` 文件中 `BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=` 被解析为空字符串 `""`。当前配置模型允许该字段**不设置**（值为 `None`），但**不允许设置为空字符串**；只要写了这个变量，就必须是合法 URL。

### 解决方案
按实际部署方式选择其一，不要把该字段保留为空字符串：

- **仅使用本地文件存储**：删除这一行，或注释掉，让变量保持“未设置”
- **启用 OSS / CDN 公网访问**：填写真实公网地址前缀
- **仅为本地调试临时过校验**：可以先填 `http://localhost`，但不要把它当成生产环境最终值

```bash
# 修改前（会报错）
BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=

# 方案 1：仅本地存储，删除这一行或注释掉
# BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=

# 方案 2：启用 OSS/CDN，填写真实公网地址
BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=https://cdn.example.com/bingwall

# 方案 3：仅本地调试临时占位
BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=http://localhost
```

> 补充说明：这个字段不只是启动校验占位；当资源记录的 `storage_backend = oss` 时，公开接口、后台接口和下载跳转都会用它来拼接真实图片 URL。

---

## 问题 4：API 返回 500 错误（数据库未初始化）

### 现象
```bash
curl http://127.0.0.1:30003/api/public/wallpapers
# Internal Server Error
```

日志显示：
```
sqlite3.OperationalError: no such table: wallpapers
```

### 原因
数据库未执行迁移，表结构不存在。

### 解决方案
运行数据库迁移：
```bash
# 先创建必要目录
mkdir -p var/data var/images/tmp var/images/public var/images/failed var/backups

# 运行迁移
.venv/bin/python -m app.repositories.migrations
```

---

## 问题 5：端口被占用导致启动失败

### 现象
```
ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 30003): address already in use
```

### 原因
端口已被其他进程占用（可能是之前的应用实例未完全退出）。

### 解决方案
```bash
# 方法 1：杀掉占用端口的进程
fuser -k 30003/tcp

# 方法 2：查找并手动终止
lsof -i :30003
kill -9 <PID>

# 然后重新启动应用
.venv/bin/python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 30003
```

---

## 问题 6：页面没有图片

### 现象
访问 `/wallpapers` 页面显示空列表，API 返回 `items: []`

### 原因
数据库为空，未采集壁纸数据。

### 解决方案
运行采集任务：
```bash
# 采集 Bing 壁纸（默认 en-US 市场，1 张）
.venv/bin/python -m app.collectors.bing --market en-US --count 8

# 采集 NASA APOD
.venv/bin/python -m app.collectors.nasa_apod --market global
```

---

## 问题 7：壁纸采集后仍不显示

### 现象
采集成功返回 `success_count=8`，但 API 仍返回 `items: []`

### 原因
采集的壁纸默认状态为 `is_public=0` 且 `content_status='draft'`，公开 API 只显示 `is_public=1` 且 `content_status='enabled'` 的壁纸。

### 解决方案
手动更新数据库将壁纸设为公开：
```bash
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('var/data/bingwall.sqlite3')
conn.execute('UPDATE wallpapers SET is_public=1, content_status=\"enabled\"')
conn.commit()
print(f'已更新 {conn.total_changes} 条记录')
conn.close()
"
```

> 注意：`content_status` 有效值为 `draft`, `enabled`, `disabled`, `deleted`，不是 `published`

---

## 问题 8：管理后台无法登录（未生成管理员账号）

### 现象
访问 `/admin/login` 登录时返回"用户名或密码错误"，不知道默认账号。

### 原因
当前版本支持在数据库初始化时自动创建默认管理员，但只有在初始化前同时配置了 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 和 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD` 时才会生效；如果这两个变量没配，`admin_users` 表就会保持为空。

### 解决方案
```bash
cp .env.example .env

# 启用首次管理员初始化
printf '\nBINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME=admin\n' >> .env
printf 'BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-strong-password\n' >> .env

mkdir -p var/data var/images/tmp var/images/public var/images/failed var/backups
.venv/bin/python -m app.repositories.migrations
```

> 说明：初始化命令只会在 `admin_users` 为空时创建一个状态为 `enabled` 的 `super_admin`。如果数据库里已经有管理员，再次执行不会覆盖原账号。

---

## 问题 9：管理员登录仍失败（状态值错误）

### 现象
创建了管理员用户，但登录仍返回"用户名或密码错误"。

### 原因
`admin_users.status` 字段的有效值是 `enabled`，不是 `active`。代码检查 `status == "enabled"`。

### 解决方案
```bash
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('var/data/bingwall.sqlite3')
conn.execute('UPDATE admin_users SET status=\"enabled\"')
conn.commit()
print('已修复状态')
conn.close()
"
```

> **status 有效值**：`enabled`（可登录）、`disabled`（禁用）

---

## 完整搭建步骤

### 1. 克隆代码并切换分支
```bash
git clone https://github.com/OborozukiNoYume/BingWall.git
cd BingWall
git checkout dev
git pull origin dev
```

### 2. 创建虚拟环境
```bash
python3 -m venv .venv
```

### 3. 安装依赖（网络不稳定时分步安装）
```bash
# 核心依赖
.venv/bin/pip install fastapi
.venv/bin/pip install Pillow
.venv/bin/pip install pydantic-settings==2.11.0 uvicorn==0.35.0

# 开发依赖
.venv/bin/pip install httpx==0.28.1 mypy==1.18.2 pytest==8.4.2 ruff==0.13.3
```

### 4. 配置环境变量
```bash
cp .env.example .env

# 仅使用本地文件存储时：不要把 BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL 留空，直接删掉这一行
sed -i '/^BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=$/d' .env

# 如果启用 OSS/CDN：改成真实公网地址前缀
# sed -i 's|^BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=$|BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL=https://cdn.example.com/bingwall|' .env

# 启用首次管理员初始化
printf '\nBINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME=admin\n' >> .env
printf 'BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-strong-password\n' >> .env
```

### 5. 初始化数据库
```bash
mkdir -p var/data var/images/tmp var/images/public var/images/failed var/backups
.venv/bin/python -m app.repositories.migrations
```

> 如果 `admin_users` 为空，且上一步已经配置了 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`，这里会自动创建一个启用中的管理员账号。

### 6. 启动应用
```bash
# 默认端口 8000
.venv/bin/python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000

# 自定义端口（如 30003）
.venv/bin/python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 30003
```

### 7. 采集壁纸
```bash
.venv/bin/python -m app.collectors.bing --market en-US --count 8
```

### 8. 发布壁纸（测试用）
```bash
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('var/data/bingwall.sqlite3')
conn.execute('UPDATE wallpapers SET is_public=1, content_status=\"enabled\"')
conn.commit()
conn.close()
"
```

### 9. 验证运行
```bash
# 公开 API
curl http://127.0.0.1:30003/api/public/wallpapers

# 管理后台登录
curl -X POST http://127.0.0.1:30003/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"'"$BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME"'","password":"<your-bootstrap-admin-password>"}'
```

---

## 注意事项

1. **网络问题**：PyPI 访问可能较慢或超时，建议使用国内镜像或耐心重试
2. **Python 版本**：项目要求 Python 3.14.2，确保版本匹配
3. **端口占用**：启动前确认目标端口未被占用，可用 `fuser -k <端口>/tcp` 清理
4. **目录权限**：确保 `./var/` 目录有写入权限（数据库和图片存储需要）
5. **壁纸状态**：采集的壁纸默认为草稿状态，需手动发布才能在公开 API 显示
6. **管理员账号**：如需首次自动创建，必须在初始化数据库前同时配置 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME` 与 `BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD`；数据库里已有管理员时不会覆盖；`status` 必须是 `enabled`（不是 `active`）
7. **OSS 公网地址配置**：`BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL` 不能写成空字符串；仅本地存储时应保持未设置，只有在资源使用 `storage_backend = oss` 时才需要配置真实公网地址

---

## 已实现功能补充

### 今日壁纸 / 随机壁纸 API

**已实现端点**：
| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/public/wallpapers/today` | GET | 返回今日壁纸，按 UTC 当天匹配 `wallpaper_date`，并优先站点默认市场 |
| `/api/public/wallpapers/random` | GET | 返回随机壁纸，仅从当前公开可见内容中随机选取 |

**返回格式**：与 `/api/public/wallpapers/{id}` 一致，返回单个壁纸详情（含图片资源 URL）

**行为说明**：
1. 两个接口都复用现有公开可见规则：仅返回已启用、允许公开、资源已就绪且处于发布时间窗口内的数据
2. `/api/public/wallpapers/today` 在当天存在多条候选时，先选默认市场；默认市场缺失时回退到当天排序最靠前的一条
3. 当无符合条件的内容时，两个接口都返回统一 `404`：`PUBLIC_WALLPAPER_NOT_FOUND`

**状态**：已实现（2026-03-27 更新）

---

### 日期范围筛选 API

**已实现能力**：公开 API 已支持按日期范围筛选壁纸

**可用参数**：
| 参数 | 类型 | 功能 |
|------|------|------|
| `date_from` | string | 开始日期（格式：YYYY-MM-DD） |
| `date_to` | string | 结束日期（格式：YYYY-MM-DD） |

**示例**：
```
GET /api/public/wallpapers?date_from=2026-03-01&date_to=2026-03-27
```

**行为说明**：
1. 两个参数都作用于 `wallpaper_date` 字段
2. 日期范围按闭区间处理，会包含开始日和结束日当天的数据
3. `date_from` 与 `date_to` 可与既有 `keyword`、`tag_keys`、地区、分辨率、排序和分页参数组合使用
4. 当同时传入两个日期且 `date_to < date_from` 时，接口返回统一 `422`：`COMMON_INVALID_ARGUMENT`
5. 当前只扩展了公开列表 API，没有同步增加公开前端日期选择器

**状态**：已实现（2026-03-27 更新）

---

## 已知问题

### Bing 壁纸全球共享相同图片

**现象**：采集不同市场（zh-CN, ja-JP, en-GB, de-DE, fr-FR 等）时，全部显示 `duplicate_count=8, success_count=0`

**原因**：Bing 壁纸全球共享相同图片 URL，不同市场只是标题/描述本地化不同。

**测试结果**（2026-03-27）：
```
en-US: success_count=8, duplicate_count=0  ✅ 首次采集成功
zh-CN: success_count=0, duplicate_count=8  ⏭️ 全部跳过
ja-JP: success_count=0, duplicate_count=8  ⏭️ 全部跳过
en-GB: success_count=0, duplicate_count=8  ⏭️ 全部跳过
de-DE: success_count=0, duplicate_count=8  ⏭️ 全部跳过
fr-FR: success_count=0, duplicate_count=8  ⏭️ 全部跳过
```

**结论**：这是 **Bing 本身的设计**，不是 bug。全球用户看到的是同一张图片，只是文字不同。

**正确做法**：
- ✅ 保留 `source_url_hash` 去重，同一图片只存一次
- ❌ 不要移除去重逻辑，否则会存储大量重复图片

**状态**：已确认，无需处理（2026-03-27 测试验证）

---

## 代码修改记录

### 2026-03-27 去重逻辑验证

**修改文件**：`app/services/source_collection.py`

**测试过程**：
1. 移除 `source_url_hash` 去重 → 采集 48 张（6 市场 × 8 天）
2. 发现全是同一张图片重复存储
3. 恢复 `source_url_hash` 去重 → 采集 8 张（唯一图片）

**最终结论**：保持原有去重逻辑不变

```python
# app/services/source_collection.py 第 269-286 行
# 两层去重检查：
# 1. business_key: (source_type, wallpaper_date, market_code)
# 2. source_url_hash: 图片 URL 哈希

existing_resource = self.repository.find_image_resource_by_source_url_hash(
    item.source_url_hash
)
if existing_resource is not None:
    # ... 跳过重复图片
    return "duplicated"
```
