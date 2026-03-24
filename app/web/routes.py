from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)


def get_assets_dir() -> Path:
    return project_root() / "web" / "public" / "assets"


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
