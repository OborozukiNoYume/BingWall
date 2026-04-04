from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)


def get_assets_dir() -> Path:
    return project_root() / "web" / "public" / "assets"


def get_admin_assets_dir() -> Path:
    return project_root() / "web" / "admin" / "assets"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_public_home_page() -> HTMLResponse:
    return render_public_page(
        page_name="home",
        page_title="BingWall | 首页",
        page_heading="每日壁纸目录",
        page_summary="从公开接口读取最新壁纸、基础说明和跳转入口。",
    )


@router.api_route("/wallpapers", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_public_wallpaper_list_page() -> HTMLResponse:
    return render_public_page(
        page_name="list",
        page_title="BingWall | 壁纸列表",
        page_heading="公开壁纸列表",
        page_summary="按地区、分辨率和分页条件浏览可公开访问的壁纸。",
    )


@router.api_route("/wallpapers/{wallpaper_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_public_wallpaper_detail_page(wallpaper_id: int) -> HTMLResponse:
    return render_public_page(
        page_name="detail",
        page_title="BingWall | 壁纸详情",
        page_heading="壁纸详情",
        page_summary="查看单张壁纸的完整说明、预览和下载能力。",
        wallpaper_id=wallpaper_id,
    )


@router.api_route("/admin/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_login_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-login",
        page_title="BingWall Admin | 登录",
        page_heading="后台登录",
        page_summary="使用后台认证接口建立受控会话，再进入内容管理与审计页面。",
    )


@router.api_route("/admin", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_wallpaper_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-wallpapers",
        page_title="BingWall Admin | 内容管理",
        page_heading="内容管理",
        page_summary="查看内容列表、资源状态和失败原因，并通过后台 API 执行启用、禁用或逻辑删除。",
    )


@router.api_route("/admin/wallpapers", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_wallpapers_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-wallpapers",
        page_title="BingWall Admin | 内容管理",
        page_heading="内容管理",
        page_summary="查看内容列表、资源状态和失败原因，并通过后台 API 执行启用、禁用或逻辑删除。",
    )


@router.api_route("/admin/wallpapers/{wallpaper_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_wallpaper_detail_page(wallpaper_id: int) -> HTMLResponse:
    return render_admin_page(
        page_name="admin-detail",
        page_title="BingWall Admin | 内容详情",
        page_heading="内容详情",
        page_summary="查看展示字段、来源字段、资源信息、当前状态和最近操作记录。",
        wallpaper_id=wallpaper_id,
    )


@router.api_route("/admin/tasks", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_collection_tasks_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-tasks",
        page_title="BingWall Admin | 采集任务",
        page_heading="采集任务",
        page_summary="创建手动采集任务，查看队列、执行统计、失败摘要和重试入口。",
    )


@router.api_route("/admin/tags", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_tags_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-tags",
        page_title="BingWall Admin | 标签管理",
        page_heading="标签管理",
        page_summary="维护标签定义、启停状态和排序权重，并为内容详情页提供可绑定标签集合。",
    )


@router.api_route("/admin/change-password", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_change_password_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-change-password",
        page_title="BingWall Admin | 修改密码",
        page_heading="修改密码",
        page_summary="校验当前密码后更新后台账号密码，并让当前账号重新登录以使旧会话失效。",
    )


@router.api_route("/admin/tasks/{task_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_collection_task_detail_page(task_id: int) -> HTMLResponse:
    return render_admin_page(
        page_name="admin-task-detail",
        page_title="BingWall Admin | 任务详情",
        page_heading="任务详情",
        page_summary="查看任务参数快照、成功/重复/失败统计和逐条处理明细。",
        task_id=task_id,
    )


@router.api_route("/admin/logs", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_collection_logs_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-logs",
        page_title="BingWall Admin | 结构化日志",
        page_heading="结构化日志",
        page_summary="按任务 ID、错误类型和时间范围查询采集任务结构化处理日志。",
    )


@router.api_route("/admin/download-stats", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_download_stats_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-download-stats",
        page_title="BingWall Admin | 下载统计",
        page_heading="下载统计",
        page_summary="查看最近一段时间的下载登记总量、热门内容和趋势变化。",
    )


@router.api_route("/admin/audit-logs", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_admin_audit_logs_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-audit",
        page_title="BingWall Admin | 审计记录",
        page_heading="审计记录",
        page_summary="按对象和时间范围查询后台审计记录，并关联操作者和 trace_id。",
    )


def render_public_page(
    *,
    page_name: str,
    page_title: str,
    page_heading: str,
    page_summary: str,
    wallpaper_id: int | None = None,
) -> HTMLResponse:
    wallpaper_id_attr = f' data-wallpaper-id="{wallpaper_id}"' if wallpaper_id is not None else ""
    home_api_shortcuts = ""
    if page_name == "home":
        home_api_shortcuts = """
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6" aria-label="公开接口快捷入口">
            <article class="grid gap-2 border border-stone-200/60 rounded-xl bg-white p-4 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200">
              <p class="text-xs font-semibold uppercase tracking-widest text-amber-600">今日壁纸 API</p>
              <code class="text-sm font-mono text-stone-600">/api/public/wallpapers/today</code>
              <a class="text-sm text-amber-600 hover:underline" href="/api/public/wallpapers/today" target="_blank" rel="noreferrer">查看接口返回</a>
            </article>
            <article class="grid gap-2 border border-stone-200/60 rounded-xl bg-white p-4 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200">
              <p class="text-xs font-semibold uppercase tracking-widest text-amber-600">随机壁纸 API</p>
              <code class="text-sm font-mono text-stone-600">/api/public/wallpapers/random</code>
              <a class="text-sm text-amber-600 hover:underline" href="/api/public/wallpapers/random" target="_blank" rel="noreferrer">查看接口返回</a>
            </article>
          </div>
        """
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{page_title}</title>
    <link rel="stylesheet" href="/assets/site.css" />
  </head>
  <body data-page="{page_name}"{wallpaper_id_attr}>
    <div class="max-w-[1180px] mx-auto px-4 pt-6 pb-12">
      <header class="flex items-center justify-between gap-4 bg-white border border-stone-200/60 rounded-2xl px-5 py-4 mb-5 shadow-sm">
        <a class="text-xl font-bold tracking-wider no-underline hover:opacity-80" href="/" data-brand-mark>BingWall</a>
        <nav class="flex gap-4 flex-wrap" aria-label="公开导航">
          <a class="text-sm font-medium text-stone-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/">首页</a>
          <a class="text-sm font-medium text-stone-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/wallpapers">壁纸列表</a>
        </nav>
      </header>
      <main class="grid gap-5">
        <section class="bg-white border border-stone-200/60 rounded-2xl p-7 shadow-sm">
          <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-amber-600">公开前端</p>
          <h1 class="text-2xl font-bold">{page_heading}</h1>
          <p class="mt-2 text-stone-600">{page_summary}</p>
          <div class="mt-4 text-sm text-stone-500" data-site-copy>
            <p class="font-semibold" data-site-name>BingWall</p>
            <p data-site-description>正在加载站点说明...</p>
          </div>
{home_api_shortcuts}
        </section>
        <section class="bg-white border border-stone-200/60 rounded-2xl p-7 shadow-sm min-h-[420px]" id="app-root" aria-live="polite">
          <noscript>
            <div class="border border-amber-300 rounded-xl bg-amber-50 p-4 shadow-sm">
              <h2 class="font-semibold">需要启用 JavaScript</h2>
              <p class="text-sm text-stone-600 mt-1">当前公开前端通过公开 API 获取数据，请启用浏览器 JavaScript 后重试。</p>
            </div>
          </noscript>
        </section>
      </main>
      <footer class="bg-white border border-stone-200/60 rounded-2xl mt-5 px-5 py-4 text-sm text-stone-500 shadow-sm">
        <p>公开页面仅通过 <code class="font-mono text-xs">/api/public/*</code> 接口读取数据。</p>
      </footer>
    </div>
    <script type="module" src="/assets/site.js"></script>
  </body>
</html>
"""
    return HTMLResponse(content=html)


def render_admin_page(
    *,
    page_name: str,
    page_title: str,
    page_heading: str,
    page_summary: str,
    wallpaper_id: int | None = None,
    task_id: int | None = None,
) -> HTMLResponse:
    wallpaper_id_attr = f' data-wallpaper-id="{wallpaper_id}"' if wallpaper_id is not None else ""
    task_id_attr = f' data-task-id="{task_id}"' if task_id is not None else ""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{page_title}</title>
    <link rel="stylesheet" href="/admin-assets/admin.css" />
  </head>
  <body data-page="{page_name}"{wallpaper_id_attr}{task_id_attr}>
    <div class="max-w-[1240px] mx-auto px-4 pt-6 pb-12">
      <header class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-slate-200/60 rounded-2xl px-6 py-5 mb-5 shadow-sm">
        <div>
          <a class="text-xl font-extrabold tracking-wider no-underline hover:opacity-80" href="/admin/wallpapers">BingWall Admin</a>
          <p class="text-sm text-slate-500 mt-1">后台页面只通过 <code class="font-mono text-xs bg-slate-100 px-1 rounded">/api/admin/*</code> 读取与修改数据。</p>
        </div>
        <nav class="flex flex-wrap gap-3" aria-label="后台导航">
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/wallpapers">内容管理</a>
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/tags">标签管理</a>
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/change-password">修改密码</a>
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/tasks">采集任务</a>
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/download-stats">下载统计</a>
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/logs">结构化日志</a>
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/audit-logs">审计记录</a>
          <a class="text-sm font-medium text-slate-600 hover:text-amber-600 no-underline px-2 py-1 rounded-lg hover:bg-amber-50" href="/admin/login">登录</a>
        </nav>
      </header>
      <main class="grid gap-5">
        <section class="bg-white border border-slate-200/60 rounded-2xl p-7 shadow-sm">
          <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-amber-600">管理后台</p>
          <h1 class="text-2xl font-bold">{page_heading}</h1>
          <p class="mt-2 text-slate-500">{page_summary}</p>
          <div class="flex items-center justify-between gap-3 mt-4">
            <p class="text-sm text-slate-500" data-admin-session>正在检查后台会话...</p>
            <button class="inline-flex items-center justify-center h-10 rounded-full border border-slate-200 bg-transparent px-4 cursor-pointer text-sm hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98]" type="button" data-admin-logout>退出登录</button>
          </div>
        </section>
        <section class="bg-white border border-slate-200/60 rounded-2xl p-7 shadow-sm min-h-[420px]" id="admin-root" aria-live="polite">
          <noscript>
            <div class="border border-orange-300 rounded-xl bg-orange-50 p-4 shadow-sm">
              <h2 class="font-semibold">需要启用 JavaScript</h2>
              <p class="text-sm text-slate-600 mt-1">当前后台页面完全依赖后台 API，请启用浏览器 JavaScript 后重试。</p>
            </div>
          </noscript>
        </section>
      </main>
    </div>
    <script type="module" src="/admin-assets/admin.js"></script>
  </body>
</html>
"""
    return HTMLResponse(content=html)
