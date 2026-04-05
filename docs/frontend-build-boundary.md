# BingWall 前端构建与静态资源边界

## 文档元信息

- 更新时间：2026-04-05T06:36:49Z
- 文档定位：约束 `web/src`、`web/public/assets`、`web/admin/assets` 的源码 / 构建产物边界与提交流程
- 适用范围：当前原生 HTML/CSS/JavaScript + Tailwind CLI 的公开站点与管理后台

## 目录职责

### `web/src`

- 只存放 Tailwind 输入文件，当前入口为 `input-public.css` 与 `input-admin.css`
- 这里是样式源码的唯一真实来源，负责声明 `@theme`、`@layer` 和 `@source`
- 不直接被浏览器访问，也不是部署时直接挂载给反向代理的目录

### `web/public/assets`

- 对应公开站点运行时静态资源，统一挂载到 `/assets/*`
- `site.js` 是手工维护的前端源码，直接被页面以 `<script type="module">` 引用
- `site.css` 是由 `web/src/input-public.css` 构建得到的产物，不应手工长期维护

### `web/admin/assets`

- 对应后台运行时静态资源，统一挂载到 `/admin-assets/*`
- `admin.js`、`modules/*.js`、`pages/*.js` 都是手工维护的前端源码
- `admin.css` 是由 `web/src/input-admin.css` 构建得到的产物，不应手工长期维护

## 构建命令

首次准备 Node 依赖：

```bash
npm ci
```

一次性重建公开站点和后台 CSS：

```bash
npm run build:css
# 或
make frontend-build
```

开发时持续监听 CSS 变化：

```bash
npm run watch:css
# 或
make frontend-watch
```

说明：

- `make css` / `make css-watch` 仍保留为底层目标，`frontend-build` / `frontend-watch` 只是更明确的统一入口
- 当前没有额外的 JavaScript bundler；`site.js`、`admin.js` 和后台页面模块都是直接提交、直接运行

## 何时需要重建

- 修改了 `web/src/input-public.css` 或 `web/src/input-admin.css`
- 在 `app/web/routes.py`、`web/public/assets/site.js`、`web/admin/assets/*.js` 中新增、删除或替换了 Tailwind 类名
- 调整了 `@theme`、`@layer`、`@source` 或任何会影响 Tailwind 输出的样式声明

以下情况通常不需要重新构建 CSS：

- 只修改了 JavaScript 业务逻辑，但没有引入新的 Tailwind 类名
- 只修改了接口请求、事件处理、数据渲染逻辑，且页面 class 字符串保持不变

## 提交流程

1. 按职责修改源码：
   - 样式变更改 `web/src/*`
   - 公开页交互改 `web/public/assets/site.js`
   - 后台交互改 `web/admin/assets/*.js`
2. 若变更涉及样式或 Tailwind 类名，执行 `npm run build:css` 或 `make frontend-build`
3. 复核 `web/public/assets/site.css` 与 `web/admin/assets/admin.css` 的 diff，确认仅包含预期构建结果
4. 提交源码时，若构建产物发生变化，必须连同 `site.css` / `admin.css` 一并提交

## 为什么构建产物需要提交

- 当前应用和部署验收直接从仓库工作树提供 `/assets/site.css` 与 `/admin-assets/admin.css`
- `make verify-deploy`、本地开发和备用 `nginx` 方案都不会在运行前自动执行 Node 构建
- 如果样式源码已改动、但构建产物未提交，部署出来的页面会继续使用旧 CSS，形成“源码与运行态不一致”

## 禁止事项

- 不要把新的样式真实来源直接写进 `web/public/assets/site.css` 或 `web/admin/assets/admin.css`
- 不要把 `web/src` 当成浏览器可直接访问的静态目录
- 不要假设目标机或 CI 会在部署前自动补跑前端构建；当前仓库口径仍是“先在仓库内构建，再提交产物”
