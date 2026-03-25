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


@router.get("/", response_class=HTMLResponse)
def get_public_home_page() -> HTMLResponse:
    return render_public_page(
        page_name="home",
        page_title="BingWall | 首页",
        page_heading="每日壁纸目录",
        page_summary="从公开接口读取最新壁纸、基础说明和跳转入口。",
    )


@router.get("/wallpapers", response_class=HTMLResponse)
def get_public_wallpaper_list_page() -> HTMLResponse:
    return render_public_page(
        page_name="list",
        page_title="BingWall | 壁纸列表",
        page_heading="公开壁纸列表",
        page_summary="按地区、分辨率和分页条件浏览可公开访问的壁纸。",
    )


@router.get("/wallpapers/{wallpaper_id}", response_class=HTMLResponse)
def get_public_wallpaper_detail_page(wallpaper_id: int) -> HTMLResponse:
    return render_public_page(
        page_name="detail",
        page_title="BingWall | 壁纸详情",
        page_heading="壁纸详情",
        page_summary="查看单张壁纸的完整说明、预览和下载能力。",
        wallpaper_id=wallpaper_id,
    )


@router.get("/admin/login", response_class=HTMLResponse)
def get_admin_login_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-login",
        page_title="BingWall Admin | 登录",
        page_heading="后台登录",
        page_summary="使用后台认证接口建立受控会话，再进入内容管理与审计页面。",
    )


@router.get("/admin", response_class=HTMLResponse)
def get_admin_wallpaper_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-wallpapers",
        page_title="BingWall Admin | 内容管理",
        page_heading="内容管理",
        page_summary="查看内容列表、资源状态和失败原因，并通过后台 API 执行启用、禁用或逻辑删除。",
    )


@router.get("/admin/wallpapers", response_class=HTMLResponse)
def get_admin_wallpapers_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-wallpapers",
        page_title="BingWall Admin | 内容管理",
        page_heading="内容管理",
        page_summary="查看内容列表、资源状态和失败原因，并通过后台 API 执行启用、禁用或逻辑删除。",
    )


@router.get("/admin/wallpapers/{wallpaper_id}", response_class=HTMLResponse)
def get_admin_wallpaper_detail_page(wallpaper_id: int) -> HTMLResponse:
    return render_admin_page(
        page_name="admin-detail",
        page_title="BingWall Admin | 内容详情",
        page_heading="内容详情",
        page_summary="查看展示字段、来源字段、资源信息、当前状态和最近操作记录。",
        wallpaper_id=wallpaper_id,
    )


@router.get("/admin/tasks", response_class=HTMLResponse)
def get_admin_collection_tasks_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-tasks",
        page_title="BingWall Admin | 采集任务",
        page_heading="采集任务",
        page_summary="创建手动采集任务，查看队列、执行统计、失败摘要和重试入口。",
    )


@router.get("/admin/tasks/{task_id}", response_class=HTMLResponse)
def get_admin_collection_task_detail_page(task_id: int) -> HTMLResponse:
    return render_admin_page(
        page_name="admin-task-detail",
        page_title="BingWall Admin | 任务详情",
        page_heading="任务详情",
        page_summary="查看任务参数快照、成功/重复/失败统计和逐条处理明细。",
        task_id=task_id,
    )


@router.get("/admin/logs", response_class=HTMLResponse)
def get_admin_collection_logs_page() -> HTMLResponse:
    return render_admin_page(
        page_name="admin-logs",
        page_title="BingWall Admin | 结构化日志",
        page_heading="结构化日志",
        page_summary="按任务 ID、错误类型和时间范围查询采集任务结构化处理日志。",
    )


@router.get("/admin/audit-logs", response_class=HTMLResponse)
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
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{page_title}</title>
    <link rel="stylesheet" href="/assets/site.css" />
  </head>
  <body data-page="{page_name}"{wallpaper_id_attr}>
    <div class="page-shell">
      <header class="masthead">
        <a class="brand-mark" href="/">BingWall</a>
        <nav class="primary-nav" aria-label="公开导航">
          <a href="/">首页</a>
          <a href="/wallpapers">壁纸列表</a>
        </nav>
      </header>
      <main class="page-main">
        <section class="hero-panel">
          <p class="eyebrow">公开前端</p>
          <h1>{page_heading}</h1>
          <p class="hero-copy">{page_summary}</p>
          <div class="site-copy" data-site-copy>
            <p class="site-name">BingWall</p>
            <p class="site-description">正在加载站点说明...</p>
          </div>
        </section>
        <section class="content-panel" id="app-root" aria-live="polite">
          <noscript>
            <div class="status-card status-card-warning">
              <h2>需要启用 JavaScript</h2>
              <p>当前公开前端通过公开 API 获取数据，请启用浏览器 JavaScript 后重试。</p>
            </div>
          </noscript>
        </section>
      </main>
      <footer class="site-footer">
        <p>公开页面仅通过 <code>/api/public/*</code> 接口读取数据。</p>
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
    <div class="admin-shell">
      <header class="admin-header">
        <div>
          <a class="admin-brand" href="/admin/wallpapers">BingWall Admin</a>
          <p class="admin-caption">后台页面只通过 <code>/api/admin/*</code> 读取与修改数据。</p>
        </div>
        <nav class="admin-nav" aria-label="后台导航">
          <a href="/admin/wallpapers">内容管理</a>
          <a href="/admin/tasks">采集任务</a>
          <a href="/admin/logs">结构化日志</a>
          <a href="/admin/audit-logs">审计记录</a>
          <a href="/admin/login">登录</a>
        </nav>
      </header>
      <main class="admin-main">
        <section class="admin-hero">
          <p class="admin-eyebrow">管理后台</p>
          <h1>{page_heading}</h1>
          <p class="admin-summary">{page_summary}</p>
          <div class="admin-session-bar">
            <p class="admin-session-copy" data-admin-session>正在检查后台会话...</p>
            <button class="ghost-button" type="button" data-admin-logout>退出登录</button>
          </div>
        </section>
        <section class="admin-panel" id="admin-root" aria-live="polite">
          <noscript>
            <div class="notice-card notice-card-warning">
              <h2>需要启用 JavaScript</h2>
              <p>当前后台页面完全依赖后台 API，请启用浏览器 JavaScript 后重试。</p>
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
