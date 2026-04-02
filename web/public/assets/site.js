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
const LOOKUP_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

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
    const nameNodes = document.querySelectorAll("[data-site-name], [data-brand-mark]");
    const descriptionNodes = document.querySelectorAll("[data-site-description]");
    document.title = document.title.replace("BingWall", data.site_name);
    nameNodes.forEach((node) => {
      node.textContent = data.site_name;
    });
    descriptionNodes.forEach((node) => {
      node.textContent = data.site_description;
    });
  } catch {
    const descriptionNode = document.querySelector("[data-site-description]");
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
      <div class="flex items-baseline justify-between gap-4 mb-5">
        <div>
          <h2 class="text-lg font-bold">最新壁纸</h2>
          <p class="text-sm text-stone-500">首页默认展示最新 6 项公开内容。</p>
        </div>
        <a class="text-sm text-amber-600 hover:underline" href="/wallpapers">查看完整列表</a>
      </div>
      <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(renderWallpaperCard).join("")}</section>
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
      ? `<a class="inline-flex items-center justify-center h-10 rounded-full bg-stone-800 hover:bg-stone-700 hover:shadow-sm active:scale-[0.98] text-white px-5 text-sm cursor-pointer no-underline" href="${escapeHtml(detail.download_url)}" target="_blank" rel="noreferrer" data-download-wallpaper-id="${escapeHtml(detail.id)}" data-download-channel="public_detail">下载原图</a>`
      : `<button class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer opacity-50" type="button" disabled>当前不可下载</button>`;

    appRoot.innerHTML = `
      <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.9fr)] gap-5">
        <section>
          <div class="overflow-hidden border border-stone-200/60 rounded-2xl bg-stone-100 min-h-[320px] shadow-sm">
            <img src="${escapeHtml(detail.preview_url)}" alt="${escapeHtml(detail.title)}" class="w-full" />
          </div>
          <div class="flex flex-wrap gap-3 mt-4">
            ${downloadBlock}
            <a class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer no-underline text-stone-600 hover:bg-stone-50 hover:border-stone-300 active:scale-[0.98]" href="/wallpapers">返回列表</a>
          </div>
        </section>
        <aside>
          <div class="border border-stone-200/60 rounded-2xl bg-stone-50 p-5 grid gap-3 shadow-sm">
            <p class="text-xs font-semibold uppercase tracking-widest text-amber-600">壁纸详情</p>
            <h2 class="text-lg font-bold">${escapeHtml(detail.title)}</h2>
            <p class="text-sm text-stone-600">${escapeHtml(detail.description || "当前没有补充说明。")}</p>
          </div>
          <div class="grid gap-0 mt-4">
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
  const selectedLookupDate = normalizeLookupDate(state.date_lookup);
  let currentState = {
    ...state,
    market_spotlight_code: selectedMarketSpotlightCode,
    date_lookup: selectedLookupDate,
  };

  appRoot.innerHTML = `
    <section class="mb-6" aria-labelledby="market-spotlight-heading">
      <div class="flex items-baseline justify-between gap-4 mb-3">
        <div>
          <h2 id="market-spotlight-heading" class="text-lg font-bold">按市场查看最新壁纸</h2>
          <p class="text-sm text-stone-500">固定支持 ${MARKET_SPOTLIGHT_OPTIONS.map((option) => escapeHtml(option.code)).join(" / ")}，单独调用公开单条接口，不影响下方分页列表。</p>
        </div>
      </div>
      <form class="grid gap-3" id="market-spotlight-form">
        <div class="grid gap-1">
          <label class="text-sm font-medium" for="market-spotlight-code">市场</label>
          <select id="market-spotlight-code" name="market_spotlight_code" class="w-full border border-stone-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none">
            ${MARKET_SPOTLIGHT_OPTIONS.map(
              (option) => `<option value="${escapeHtml(option.code)}" ${selectedMarketSpotlightCode === option.code ? "selected" : ""}>${escapeHtml(option.code)} | ${escapeHtml(option.label)}</option>`,
            ).join("")}
          </select>
        </div>
      </form>
      <div id="market-spotlight-result" aria-live="polite" class="mt-3"></div>
    </section>
    <section class="mb-6" aria-labelledby="date-lookup-heading">
      <div class="flex items-baseline justify-between gap-4 mb-3">
        <div>
          <h2 id="date-lookup-heading" class="text-lg font-bold">按日期查找壁纸</h2>
          <p class="text-sm text-stone-500">选择一个 <code class="font-mono text-xs bg-stone-100 px-1 rounded">YYYY-MM-DD</code> 日期，单独调用公开单条接口查找当天对应的公开壁纸，不影响下方分页列表。</p>
        </div>
      </div>
      <form class="grid gap-3" id="date-lookup-form">
        <div class="grid gap-1">
          <label class="text-sm font-medium" for="date-lookup-input">日期</label>
          <input id="date-lookup-input" name="date_lookup" type="date" value="${escapeHtml(selectedLookupDate)}" class="w-full border border-stone-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none" />
        </div>
        <div class="flex flex-wrap gap-3">
          <button class="inline-flex items-center justify-center h-10 rounded-full bg-stone-800 hover:bg-stone-700 hover:shadow-sm active:scale-[0.98] text-white px-5 text-sm cursor-pointer border-0" type="submit">查找壁纸</button>
        </div>
      </form>
      <div id="date-lookup-result" aria-live="polite" class="mt-3"></div>
    </section>
    <div class="flex items-baseline justify-between gap-4 mb-4">
      <div>
        <h2 class="text-lg font-bold">筛选公开壁纸</h2>
        <p class="text-sm text-stone-500">只显示已启用、允许公开、资源已就绪且处于发布时间窗口内的内容。</p>
      </div>
      <p class="text-sm text-stone-500">第 ${page} 页 / 共 ${totalPages || 1} 页</p>
    </div>
    <form class="grid gap-4 mb-5" id="wallpaper-filter-form">
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div class="grid gap-1">
          <label class="text-sm font-medium" for="keyword">关键词</label>
          <input id="keyword" name="keyword" type="search" placeholder="标题、说明、版权或标签" class="w-full border border-stone-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none" />
        </div>
        <div class="grid gap-1">
          <label class="text-sm font-medium" for="market-code">地区</label>
          <select id="market-code" name="market_code" class="w-full border border-stone-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none">
            <option value="">全部地区</option>
            ${markets.map((market) => `<option value="${escapeHtml(market.code)}">${escapeHtml(market.label)}</option>`).join("")}
          </select>
        </div>
        <div class="grid gap-1">
          <label class="text-sm font-medium" for="resolution-min-width">最小宽度</label>
          <input id="resolution-min-width" name="resolution_min_width" type="number" min="1" placeholder="例如 1920" class="w-full border border-stone-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none" />
        </div>
        <div class="grid gap-1">
          <label class="text-sm font-medium" for="resolution-min-height">最小高度</label>
          <input id="resolution-min-height" name="resolution_min_height" type="number" min="1" placeholder="例如 1080" class="w-full border border-stone-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none" />
        </div>
        <div class="grid gap-1">
          <label class="text-sm font-medium" for="page-size">每页数量</label>
          <select id="page-size" name="page_size" class="w-full border border-stone-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none">
            <option value="12">12</option>
            <option value="20">20</option>
            <option value="40">40</option>
          </select>
        </div>
      </div>
      <div class="grid gap-1">
        <label class="text-sm font-medium">标签</label>
        ${
          tags.length === 0
            ? `<div class="border border-stone-200 rounded-xl bg-stone-50 p-4 text-sm text-stone-500">当前没有可公开筛选的标签。</div>`
            : `<div class="flex flex-wrap gap-2">
                ${tags
                  .map(
                    (tag) => `
                      <label class="inline-flex items-center gap-2 border border-stone-200 rounded-full bg-white px-3 py-2 cursor-pointer text-sm hover:bg-stone-50 hover:border-stone-300 transition-colors duration-150">
                        <input type="checkbox" name="tag_keys" value="${escapeHtml(tag.tag_key)}" ${selectedTagKeys.includes(tag.tag_key) ? "checked" : ""} />
                        <span>${escapeHtml(tag.tag_name)}</span>
                      </label>
                    `,
                  )
                  .join("")}
              </div>`
        }
      </div>
      <div class="flex flex-wrap gap-3">
        <button class="inline-flex items-center justify-center h-10 rounded-full bg-stone-800 hover:bg-stone-700 hover:shadow-sm active:scale-[0.98] text-white px-5 text-sm cursor-pointer border-0" type="submit">刷新结果</button>
        <button class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer text-stone-600 hover:bg-stone-50 hover:border-stone-300 active:scale-[0.98]" id="reset-filters" type="button">重置筛选</button>
      </div>
    </form>
    <section id="wallpaper-list-results"></section>
    <nav class="flex flex-wrap gap-3 mt-4" id="wallpaper-pagination" aria-label="分页导航"></nav>
  `;

  const filterForm = document.querySelector("#wallpaper-filter-form");
  const marketSpotlightForm = document.querySelector("#market-spotlight-form");
  const marketSpotlightResult = document.querySelector("#market-spotlight-result");
  const dateLookupForm = document.querySelector("#date-lookup-form");
  const dateLookupResult = document.querySelector("#date-lookup-result");
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

  if (dateLookupForm instanceof HTMLFormElement && dateLookupResult instanceof HTMLElement) {
    void renderDateLookup(dateLookupResult, selectedLookupDate);
    dateLookupForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(dateLookupForm);
      const nextLookupDate = normalizeLookupDate(stringOrNull(formData.get("date_lookup")));
      currentState = {
        ...currentState,
        date_lookup: nextLookupDate,
      };
      replaceListState({
        ...currentState,
      });
      await renderDateLookup(dateLookupResult, nextLookupDate);
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
    resultsNode.innerHTML = `<section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(renderWallpaperCard).join("")}</section>`;
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
      date_lookup: currentState.date_lookup,
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
        date_lookup: currentState.date_lookup,
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
  return renderFeatureWallpaperMarkup(detail, "市场最新公开壁纸");
}

async function renderDateLookup(container, lookupDate) {
  if (!lookupDate) {
    container.innerHTML = renderStatusMarkup({
      title: "请选择日期",
      copy: "选择一个日期后，页面会按该日期精确查找一张公开壁纸。",
    });
    return;
  }

  container.innerHTML = renderStatusMarkup({
    title: "正在读取日期结果",
    copy: `正在加载 ${lookupDate} 的公开壁纸...`,
  });

  try {
    const detail = await fetchEnvelope(`/api/public/wallpapers/by-date/${encodeURIComponent(lookupDate)}`);
    container.innerHTML = renderDateLookupMarkup(detail);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      container.innerHTML = renderStatusMarkup({
        title: "当前日期暂无公开壁纸",
        copy: `${lookupDate} 暂时没有可展示内容，可以换一个日期后重试。`,
      });
      return;
    }

    console.error(error);
    container.innerHTML = renderStatusMarkup({
      title: "日期结果读取失败",
      copy: "公开接口暂时不可用，请稍后重试。",
    });
  }
}

function renderDateLookupMarkup(detail) {
  return renderFeatureWallpaperMarkup(detail, "精确日期结果");
}

function renderFeatureWallpaperMarkup(detail, eyebrow) {
  const downloadMarkup =
    detail.is_downloadable && detail.download_url
      ? `<a class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer no-underline text-stone-600 hover:bg-stone-50 hover:border-stone-300 active:scale-[0.98]" href="${escapeHtml(detail.download_url)}" target="_blank" rel="noreferrer">下载当前默认分辨率</a>`
      : `<button class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer opacity-50" type="button" disabled>当前不可下载</button>`;

  return `
    <article class="grid grid-cols-1 md:grid-cols-[minmax(280px,1.2fr)_minmax(0,1fr)] gap-4 border border-stone-200/60 rounded-2xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow duration-200">
      <a class="block aspect-[16/10] bg-stone-100 overflow-hidden" href="/wallpapers/${escapeHtml(detail.id)}">
        <img src="${escapeHtml(detail.preview_url)}" alt="${escapeHtml(detail.title)}" loading="lazy" class="w-full h-full object-cover" />
      </a>
      <div class="grid gap-3 p-5 content-start">
        <p class="text-xs font-semibold uppercase tracking-widest text-amber-600">${escapeHtml(eyebrow)}</p>
        <h3 class="font-bold"><a href="/wallpapers/${escapeHtml(detail.id)}" class="hover:text-amber-600 no-underline">${escapeHtml(detail.title)}</a></h3>
        <p class="text-sm text-stone-600">${escapeHtml(detail.description || detail.subtitle || "当前没有补充说明。")}</p>
        <div class="flex flex-wrap gap-2 text-sm text-stone-500">
          <span class="bg-stone-100 rounded-full px-2.5 py-0.5 text-xs">${escapeHtml(detail.market_code)}</span>
          <span class="bg-stone-100 rounded-full px-2.5 py-0.5 text-xs">${escapeHtml(detail.wallpaper_date)}</span>
          <span class="bg-stone-100 rounded-full px-2.5 py-0.5 text-xs">${escapeHtml(formatResolution(detail.width, detail.height))}</span>
        </div>
        <div class="flex flex-wrap gap-3">
          <a class="inline-flex items-center justify-center h-10 rounded-full bg-stone-800 hover:bg-stone-700 hover:shadow-sm active:scale-[0.98] text-white px-5 text-sm cursor-pointer no-underline" href="/wallpapers/${escapeHtml(detail.id)}">查看详情</a>
          ${downloadMarkup}
        </div>
      </div>
    </article>
  `;
}

function renderWallpaperCard(item) {
  return `
    <article class="group grid gap-0 border border-stone-200/60 rounded-2xl overflow-hidden bg-white shadow-sm hover:shadow-md hover:-translate-y-0.5">
      <a class="block aspect-[16/10] bg-stone-100 overflow-hidden" href="${escapeHtml(item.detail_url)}">
        <img src="${escapeHtml(item.thumbnail_url)}" alt="${escapeHtml(item.title)}" loading="lazy" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" />
      </a>
      <div class="grid gap-2 p-4">
        <h3 class="font-bold text-sm"><a href="${escapeHtml(item.detail_url)}" class="hover:text-amber-600 no-underline">${escapeHtml(item.title)}</a></h3>
        <p class="text-sm text-stone-500">${escapeHtml(item.subtitle || "当前没有补充副标题。")}</p>
        <div class="flex flex-wrap gap-2 text-stone-500">
          <span class="bg-stone-100 rounded-full px-2.5 py-0.5 text-xs">${escapeHtml(item.market_code)}</span>
          <span class="bg-stone-100 rounded-full px-2.5 py-0.5 text-xs">${escapeHtml(item.wallpaper_date)}</span>
        </div>
      </div>
    </article>
  `;
}

function renderMetaItem(label, value) {
  return `
    <div class="border-t border-stone-100 py-3 px-1 grid gap-0.5">
      <strong class="text-sm">${escapeHtml(label)}</strong>
      <p class="text-sm text-stone-600">${escapeHtml(value)}</p>
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
    links.push(`<a class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer no-underline text-stone-600 hover:bg-stone-50 hover:border-stone-300 active:scale-[0.98]" href="${buildListHref({ ...state, page: String(prevPage) })}" data-page-target="${prevPage}">上一页</a>`);
  }

  if (nextPage) {
    links.push(`<a class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer no-underline text-stone-600 hover:bg-stone-50 hover:border-stone-300 active:scale-[0.98]" href="${buildListHref({ ...state, page: String(nextPage) })}" data-page-target="${nextPage}">下一页</a>`);
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
    date_lookup: normalizeLookupDate(params.get("date_lookup")),
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

function normalizeLookupDate(value) {
  if (typeof value !== "string") {
    return "";
  }
  const trimmedValue = value.trim();
  return LOOKUP_DATE_PATTERN.test(trimmedValue) ? trimmedValue : "";
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
      ? `<div class="flex flex-wrap gap-3"><a class="inline-flex items-center justify-center h-10 rounded-full border border-stone-200 bg-white px-5 text-sm cursor-pointer no-underline text-stone-600 hover:bg-stone-50 hover:border-stone-300 active:scale-[0.98]" href="${escapeHtml(actionHref)}">${escapeHtml(actionLabel)}</a></div>`
      : "";

  return `
    <div class="border border-stone-200/60 rounded-2xl bg-stone-50 p-5 grid gap-3 shadow-sm">
      <h2 class="font-semibold">${escapeHtml(title)}</h2>
      <p class="text-sm text-stone-600">${escapeHtml(copy)}</p>
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
