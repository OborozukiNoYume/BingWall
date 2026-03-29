const appRoot = document.querySelector("#app-root");
const body = document.body;
const pageName = body.dataset.page;
const wallpaperId = body.dataset.wallpaperId;
const MARKET_SPOTLIGHT_OPTIONS = [
  { code: "zh-CN", label: "中文（中国）" },
  { code: "en-US", label: "English (United States)" },
  { code: "ja-JP", label: "日本語（日本）" },
];
const DEFAULT_MARKET_SPOTLIGHT_CODE = MARKET_SPOTLIGHT_OPTIONS[0].code;

document.addEventListener("DOMContentLoaded", async () => {
  await loadSiteInfo();

  if (!(appRoot instanceof HTMLElement)) {
    return;
  }

  if (pageName === "home") {
    await renderHomePage();
    return;
  }

  if (pageName === "list") {
    await renderListPage();
    return;
  }

  if (pageName === "detail" && wallpaperId) {
    await renderDetailPage(wallpaperId);
  }
});

async function loadSiteInfo() {
  try {
    const data = await fetchEnvelope("/api/public/site-info");
    const nameNodes = document.querySelectorAll(".site-name, .brand-mark");
    const descriptionNodes = document.querySelectorAll(".site-description");
    document.title = document.title.replace("BingWall", data.site_name);
    nameNodes.forEach((node) => {
      node.textContent = data.site_name;
    });
    descriptionNodes.forEach((node) => {
      node.textContent = data.site_description;
    });
  } catch {
    const descriptionNode = document.querySelector(".site-description");
    if (descriptionNode instanceof HTMLElement) {
      descriptionNode.textContent = "公开站点说明暂时不可用，请稍后重试。";
    }
  }
}

async function renderHomePage() {
  setLoadingState("正在读取最新壁纸...");

  try {
    const response = await fetchEnvelope("/api/public/wallpapers?page=1&page_size=6&sort=date_desc");
    const items = Array.isArray(response.items) ? response.items : [];

    if (items.length === 0) {
      setStatusCard({
        title: "当前没有可公开展示的壁纸",
        copy: "内容可能尚未发布，或正在等待新的采集结果。",
        actionHref: "/wallpapers",
        actionLabel: "前往列表页",
      });
      return;
    }

    appRoot.innerHTML = `
      <div class="section-head">
        <div>
          <h2>最新壁纸</h2>
          <p class="meta-note">首页默认展示最新 6 项公开内容。</p>
        </div>
        <a class="button-link" href="/wallpapers">查看完整列表</a>
      </div>
      <section class="card-grid">${items.map(renderWallpaperCard).join("")}</section>
    `;
  } catch (error) {
    setServiceBusyState(error);
  }
}

async function renderListPage() {
  setLoadingState("正在读取筛选项和列表结果...");

  try {
    const [filters, listPayload] = await Promise.all([
      fetchEnvelope("/api/public/wallpaper-filters"),
      fetchListPayload(readListState()),
    ]);
    renderListView({
      filters,
      listPayload,
      state: readListState(),
    });
  } catch (error) {
    setServiceBusyState(error);
  }
}

async function renderDetailPage(id) {
  setLoadingState("正在读取壁纸详情...");

  try {
    const detail = await fetchEnvelope(`/api/public/wallpapers/${encodeURIComponent(id)}`);
    const downloadBlock = detail.is_downloadable
      ? `<a class="button" href="${escapeHtml(detail.download_url)}" target="_blank" rel="noreferrer" data-download-wallpaper-id="${escapeHtml(detail.id)}" data-download-channel="public_detail">下载原图</a>`
      : `<button class="button-secondary" type="button" disabled>当前不可下载</button>`;

    appRoot.innerHTML = `
      <div class="detail-layout">
        <section class="detail-media">
          <div class="detail-preview">
            <img src="${escapeHtml(detail.preview_url)}" alt="${escapeHtml(detail.title)}" />
          </div>
          <div class="button-row">
            ${downloadBlock}
            <a class="button-secondary" href="/wallpapers">返回列表</a>
          </div>
        </section>
        <aside class="detail-meta">
          <div class="status-card">
            <p class="eyebrow">壁纸详情</p>
            <h2>${escapeHtml(detail.title)}</h2>
            <p class="detail-copy">${escapeHtml(detail.description || "当前没有补充说明。")}</p>
          </div>
          <div class="meta-list">
            ${renderMetaItem("版权信息", detail.copyright_text || "未提供")}
            ${renderMetaItem("发布日期", detail.wallpaper_date)}
            ${renderMetaItem("地区", detail.market_code)}
            ${renderMetaItem("来源", detail.source_name)}
            ${renderMetaItem("尺寸", formatResolution(detail.width, detail.height))}
          </div>
        </aside>
      </div>
    `;
    bindDownloadAction(detail);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      setStatusCard({
        title: "内容不存在",
        copy: "这张壁纸可能尚未发布，或已经不再公开展示。",
        actionHref: "/wallpapers",
        actionLabel: "返回列表页",
      });
      return;
    }

    setServiceBusyState(error);
  }
}

function bindDownloadAction(detail) {
  const downloadLink = document.querySelector("[data-download-wallpaper-id]");
  if (!(downloadLink instanceof HTMLAnchorElement)) {
    return;
  }

  downloadLink.addEventListener("click", async (event) => {
    event.preventDefault();
    const fallbackUrl = downloadLink.href;
    const originalLabel = downloadLink.textContent || "下载原图";
    downloadLink.textContent = "正在登记下载...";
    downloadLink.setAttribute("aria-busy", "true");

    try {
      const response = await fetchDownloadEvent({
        wallpaper_id: Number(detail.id),
        download_channel: "public_detail",
      });
      openDownloadTarget(response.redirect_url);
    } catch (error) {
      console.error(error);
      if (error instanceof ApiError && (error.status === 404 || error.status === 409 || error.status === 422)) {
        window.alert(error.message);
      } else {
        openDownloadTarget(fallbackUrl);
      }
    } finally {
      downloadLink.textContent = originalLabel;
      downloadLink.removeAttribute("aria-busy");
    }
  });
}

function renderListView({ filters, listPayload, state }) {
  const markets = Array.isArray(filters.markets) ? filters.markets : [];
  const tags = Array.isArray(filters.tags) ? filters.tags : [];
  const items = Array.isArray(listPayload.data.items) ? listPayload.data.items : [];
  const pagination = listPayload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };
  const page = Number(pagination.page || 1);
  const totalPages = Number(pagination.total_pages || 0);
  const selectedTagKeys = parseTagKeys(state.tag_keys);
  const selectedMarketSpotlightCode = normalizeMarketSpotlightCode(state.market_spotlight_code);
  let currentState = {
    ...state,
    market_spotlight_code: selectedMarketSpotlightCode,
  };

  appRoot.innerHTML = `
    <section class="market-spotlight-panel" aria-labelledby="market-spotlight-heading">
      <div class="section-head">
        <div>
          <h2 id="market-spotlight-heading">按市场查看最新壁纸</h2>
          <p class="meta-note">固定支持 ${MARKET_SPOTLIGHT_OPTIONS.map((option) => escapeHtml(option.code)).join(" / ")}，单独调用公开单条接口，不影响下方分页列表。</p>
        </div>
      </div>
      <form class="market-spotlight-form" id="market-spotlight-form">
        <div class="field">
          <label for="market-spotlight-code">市场</label>
          <select id="market-spotlight-code" name="market_spotlight_code">
            ${MARKET_SPOTLIGHT_OPTIONS.map(
              (option) => `<option value="${escapeHtml(option.code)}" ${selectedMarketSpotlightCode === option.code ? "selected" : ""}>${escapeHtml(option.code)} | ${escapeHtml(option.label)}</option>`,
            ).join("")}
          </select>
        </div>
      </form>
      <div class="market-spotlight-result" id="market-spotlight-result" aria-live="polite"></div>
    </section>
    <div class="section-head">
      <div>
        <h2>筛选公开壁纸</h2>
        <p class="meta-note">只显示已启用、允许公开、资源已就绪且处于发布时间窗口内的内容。</p>
      </div>
      <p class="pagination-note">第 ${page} 页 / 共 ${totalPages || 1} 页</p>
    </div>
    <form class="filter-form" id="wallpaper-filter-form">
      <div class="filter-grid">
        <div class="field">
          <label for="keyword">关键词</label>
          <input id="keyword" name="keyword" type="search" placeholder="标题、说明、版权或标签" />
        </div>
        <div class="field">
          <label for="market-code">地区</label>
          <select id="market-code" name="market_code">
            <option value="">全部地区</option>
            ${markets.map((market) => `<option value="${escapeHtml(market.code)}">${escapeHtml(market.label)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="resolution-min-width">最小宽度</label>
          <input id="resolution-min-width" name="resolution_min_width" type="number" min="1" placeholder="例如 1920" />
        </div>
        <div class="field">
          <label for="resolution-min-height">最小高度</label>
          <input id="resolution-min-height" name="resolution_min_height" type="number" min="1" placeholder="例如 1080" />
        </div>
        <div class="field">
          <label for="page-size">每页数量</label>
          <select id="page-size" name="page_size">
            <option value="12">12</option>
            <option value="20">20</option>
            <option value="40">40</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>标签</label>
        ${
          tags.length === 0
            ? `<div class="status-card"><p class="status-copy">当前没有可公开筛选的标签。</p></div>`
            : `<div class="tag-filter-grid">
                ${tags
                  .map(
                    (tag) => `
                      <label class="tag-filter-chip">
                        <input type="checkbox" name="tag_keys" value="${escapeHtml(tag.tag_key)}" ${selectedTagKeys.includes(tag.tag_key) ? "checked" : ""} />
                        <span>${escapeHtml(tag.tag_name)}</span>
                      </label>
                    `,
                  )
                  .join("")}
              </div>`
        }
      </div>
      <div class="button-row">
        <button class="button" type="submit">刷新结果</button>
        <button class="button-secondary" id="reset-filters" type="button">重置筛选</button>
      </div>
    </form>
    <section id="wallpaper-list-results"></section>
    <nav class="pagination" id="wallpaper-pagination" aria-label="分页导航"></nav>
  `;

  const filterForm = document.querySelector("#wallpaper-filter-form");
  const marketSpotlightForm = document.querySelector("#market-spotlight-form");
  const marketSpotlightResult = document.querySelector("#market-spotlight-result");
  const resultsNode = document.querySelector("#wallpaper-list-results");
  const paginationNode = document.querySelector("#wallpaper-pagination");

  if (!(filterForm instanceof HTMLFormElement) || !(resultsNode instanceof HTMLElement) || !(paginationNode instanceof HTMLElement)) {
    return;
  }

  if (marketSpotlightForm instanceof HTMLFormElement && marketSpotlightResult instanceof HTMLElement) {
    void renderMarketSpotlight(marketSpotlightResult, selectedMarketSpotlightCode);
    marketSpotlightForm.addEventListener("change", async () => {
      const formData = new FormData(marketSpotlightForm);
      const nextMarketSpotlightCode = normalizeMarketSpotlightCode(
        stringOrNull(formData.get("market_spotlight_code")),
      );
      currentState = {
        ...currentState,
        market_spotlight_code: nextMarketSpotlightCode,
      };
      replaceListState({
        ...currentState,
      });
      await renderMarketSpotlight(marketSpotlightResult, nextMarketSpotlightCode);
    });
  }

  assignListFormValues(filterForm, state);

  if (items.length === 0) {
    resultsNode.innerHTML = renderStatusMarkup({
      title: "没有找到匹配的结果",
      copy: "可以尝试切换地区、降低分辨率条件，或稍后再来查看。",
      actionHref: "/",
      actionLabel: "返回首页",
    });
  } else {
    resultsNode.innerHTML = `<section class="card-grid">${items.map(renderWallpaperCard).join("")}</section>`;
  }

  paginationNode.innerHTML = renderPagination(page, totalPages, state);

  filterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const nextState = {
      keyword: stringOrNull(formData.get("keyword")),
      market_code: stringOrNull(formData.get("market_code")),
      tag_keys: formData.getAll("tag_keys").map((value) => stringOrNull(value)).filter(Boolean).join(","),
      resolution_min_width: stringOrNull(formData.get("resolution_min_width")),
      resolution_min_height: stringOrNull(formData.get("resolution_min_height")),
      page_size: stringOrNull(formData.get("page_size")) || "20",
      market_spotlight_code: currentState.market_spotlight_code,
      page: "1",
      sort: "date_desc",
    };
    await refreshListState(nextState);
  });

  const resetButton = document.querySelector("#reset-filters");
  if (resetButton instanceof HTMLButtonElement) {
    resetButton.addEventListener("click", async () => {
      await refreshListState({
        keyword: "",
        market_code: "",
        page: "1",
        page_size: "20",
        resolution_min_width: "",
        resolution_min_height: "",
        sort: "date_desc",
        tag_keys: "",
        market_spotlight_code: currentState.market_spotlight_code,
      });
    });
  }

  paginationNode.querySelectorAll("[data-page-target]").forEach((node) => {
    if (!(node instanceof HTMLAnchorElement)) {
      return;
    }
    node.addEventListener("click", async (event) => {
      event.preventDefault();
      const nextPage = node.dataset.pageTarget;
      if (!nextPage) {
        return;
      }
      await refreshListState({ ...currentState, page: nextPage, sort: "date_desc" });
    });
  });
}

async function renderMarketSpotlight(container, marketCode) {
  container.innerHTML = renderStatusMarkup({
    title: "正在读取市场结果",
    copy: `正在加载 ${marketCode} 的最新公开壁纸...`,
  });

  try {
    const detail = await fetchEnvelope(`/api/public/wallpapers/by-market/${encodeURIComponent(marketCode)}`);
    container.innerHTML = renderMarketSpotlightMarkup(detail);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      container.innerHTML = renderStatusMarkup({
        title: "当前市场暂无公开壁纸",
        copy: `${marketCode} 暂时没有可展示内容，可以切换其他市场后重试。`,
      });
      return;
    }

    console.error(error);
    container.innerHTML = renderStatusMarkup({
      title: "市场结果读取失败",
      copy: "公开接口暂时不可用，请稍后重试。",
    });
  }
}

function renderMarketSpotlightMarkup(detail) {
  const downloadMarkup =
    detail.is_downloadable && detail.download_url
      ? `<a class="button-secondary" href="${escapeHtml(detail.download_url)}" target="_blank" rel="noreferrer">下载当前默认分辨率</a>`
      : `<button class="button-secondary" type="button" disabled>当前不可下载</button>`;

  return `
    <article class="market-spotlight-card">
      <a class="market-spotlight-media" href="/wallpapers/${escapeHtml(detail.id)}">
        <img src="${escapeHtml(detail.preview_url)}" alt="${escapeHtml(detail.title)}" loading="lazy" />
      </a>
      <div class="market-spotlight-body">
        <p class="eyebrow">市场最新公开壁纸</p>
        <h3><a href="/wallpapers/${escapeHtml(detail.id)}">${escapeHtml(detail.title)}</a></h3>
        <p class="detail-copy">${escapeHtml(detail.description || detail.subtitle || "当前没有补充说明。")}</p>
        <div class="wallpaper-meta">
          <span>${escapeHtml(detail.market_code)}</span>
          <span>${escapeHtml(detail.wallpaper_date)}</span>
          <span>${escapeHtml(formatResolution(detail.width, detail.height))}</span>
        </div>
        <div class="button-row">
          <a class="button" href="/wallpapers/${escapeHtml(detail.id)}">查看详情</a>
          ${downloadMarkup}
        </div>
      </div>
    </article>
  `;
}

function renderWallpaperCard(item) {
  return `
    <article class="wallpaper-card">
      <a class="wallpaper-card-media" href="${escapeHtml(item.detail_url)}">
        <img src="${escapeHtml(item.thumbnail_url)}" alt="${escapeHtml(item.title)}" loading="lazy" />
      </a>
      <div class="wallpaper-card-body">
        <h3><a href="${escapeHtml(item.detail_url)}">${escapeHtml(item.title)}</a></h3>
        <p class="detail-copy">${escapeHtml(item.subtitle || "当前没有补充副标题。")}</p>
        <div class="wallpaper-meta">
          <span>${escapeHtml(item.market_code)}</span>
          <span>${escapeHtml(item.wallpaper_date)}</span>
        </div>
      </div>
    </article>
  `;
}

function renderMetaItem(label, value) {
  return `
    <div class="meta-item">
      <strong>${escapeHtml(label)}</strong>
      <p>${escapeHtml(value)}</p>
    </div>
  `;
}

function renderPagination(currentPage, totalPages, state) {
  if (!totalPages || totalPages <= 1) {
    return "";
  }

  const prevPage = currentPage > 1 ? currentPage - 1 : null;
  const nextPage = currentPage < totalPages ? currentPage + 1 : null;
  const links = [];

  if (prevPage) {
    links.push(`<a class="button-secondary" href="${buildListHref({ ...state, page: String(prevPage) })}" data-page-target="${prevPage}">上一页</a>`);
  }

  if (nextPage) {
    links.push(`<a class="button-secondary" href="${buildListHref({ ...state, page: String(nextPage) })}" data-page-target="${nextPage}">下一页</a>`);
  }

  return links.join("");
}

function buildListHref(state) {
  const params = new URLSearchParams();
  Object.entries(state).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  return `/wallpapers?${params.toString()}`;
}

async function refreshListState(state) {
  replaceListState(state);
  await renderListPage();
}

function replaceListState(state) {
  const url = buildListHref(state);
  window.history.replaceState({}, "", url);
}

async function fetchListPayload(state) {
  const params = new URLSearchParams();
  params.set("page", state.page || "1");
  params.set("page_size", state.page_size || "20");
  params.set("sort", "date_desc");

  if (state.market_code) {
    params.set("market_code", state.market_code);
  }
  if (state.keyword) {
    params.set("keyword", state.keyword);
  }
  if (state.tag_keys) {
    params.set("tag_keys", state.tag_keys);
  }
  if (state.resolution_min_width) {
    params.set("resolution_min_width", state.resolution_min_width);
  }
  if (state.resolution_min_height) {
    params.set("resolution_min_height", state.resolution_min_height);
  }

  const response = await fetch(`/api/public/wallpapers?${params.toString()}`, {
    headers: { Accept: "application/json" },
  });
  const payload = await response.json();
  if (!response.ok || payload.success !== true) {
    throw new ApiError(response.status, payload.message || "公开列表读取失败");
  }
  return payload;
}

function readListState() {
  const params = new URLSearchParams(window.location.search);
  return {
    keyword: params.get("keyword") || "",
    market_code: params.get("market_code") || "",
    tag_keys: params.get("tag_keys") || "",
    resolution_min_width: params.get("resolution_min_width") || "",
    resolution_min_height: params.get("resolution_min_height") || "",
    market_spotlight_code: normalizeMarketSpotlightCode(params.get("market_spotlight_code")),
    page: params.get("page") || "1",
    page_size: params.get("page_size") || "20",
    sort: "date_desc",
  };
}

function assignListFormValues(form, state) {
  setFieldValue(form, "keyword", state.keyword);
  setFieldValue(form, "market_code", state.market_code);
  setFieldValue(form, "resolution_min_width", state.resolution_min_width);
  setFieldValue(form, "resolution_min_height", state.resolution_min_height);
  setFieldValue(form, "page_size", state.page_size || "20");
  const selectedTagKeys = parseTagKeys(state.tag_keys);
  form.querySelectorAll('input[name="tag_keys"]').forEach((node) => {
    if (!(node instanceof HTMLInputElement)) {
      return;
    }
    node.checked = selectedTagKeys.includes(node.value);
  });
}

function setFieldValue(form, name, value) {
  const field = form.elements.namedItem(name);
  if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement) {
    field.value = value || "";
  }
}

function normalizeMarketSpotlightCode(value) {
  const matchedOption = MARKET_SPOTLIGHT_OPTIONS.find((option) => option.code === value);
  return matchedOption ? matchedOption.code : DEFAULT_MARKET_SPOTLIGHT_CODE;
}

async function fetchEnvelope(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const payload = await response.json();
  if (!response.ok || payload.success !== true) {
    throw new ApiError(response.status, payload.message || "公开接口请求失败");
  }
  return payload.data;
}

async function fetchDownloadEvent(payload) {
  const response = await fetch("/api/public/download-events", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.success !== true) {
    throw new ApiError(response.status, data.message || "下载登记失败");
  }
  return data.data;
}

function setLoadingState(copy) {
  if (!(appRoot instanceof HTMLElement)) {
    return;
  }
  appRoot.innerHTML = renderStatusMarkup({
    title: "正在加载",
    copy,
  });
}

function setStatusCard({ title, copy, actionHref, actionLabel }) {
  if (!(appRoot instanceof HTMLElement)) {
    return;
  }
  appRoot.innerHTML = renderStatusMarkup({ title, copy, actionHref, actionLabel });
}

function setServiceBusyState(error) {
  console.error(error);
  setStatusCard({
    title: "服务繁忙",
    copy: "公开接口暂时不可用，请稍后刷新页面重试。",
    actionHref: "/wallpapers",
    actionLabel: "重试列表页",
  });
}

function renderStatusMarkup({ title, copy, actionHref, actionLabel }) {
  const actionMarkup =
    actionHref && actionLabel
      ? `<div class="button-row"><a class="button-secondary" href="${escapeHtml(actionHref)}">${escapeHtml(actionLabel)}</a></div>`
      : "";

  return `
    <div class="status-card">
      <h2>${escapeHtml(title)}</h2>
      <p class="status-copy">${escapeHtml(copy)}</p>
      ${actionMarkup}
    </div>
  `;
}

function formatResolution(width, height) {
  if (!width || !height) {
    return "尺寸信息暂未提供";
  }
  return `${width} × ${height}`;
}

function stringOrNull(value) {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
}

function parseTagKeys(value) {
  if (!value) {
    return [];
  }
  return String(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function openDownloadTarget(url) {
  const popup = window.open(url, "_blank", "noopener,noreferrer");
  if (popup === null) {
    window.location.assign(url);
  }
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
