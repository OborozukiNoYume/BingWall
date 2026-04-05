import {
  adminRoot,
  ApiError,
  assignFormValue,
  buildWallpaperListParams,
  escapeHtml,
  fetchAdmin,
  formatBytes,
  formatResolution,
  handleAdminError,
  readWallpaperListState,
  redirectTo,
  renderDetailRow,
  renderPaginationLinks,
  setLoadingState,
  setNotice,
  statusBadgeClasses,
  stringValue,
  TW,
} from "../modules/core.js";

export async function renderWallpaperListPage(session) {
  setLoadingState("正在读取后台内容列表...");

  try {
    const state = readWallpaperListState();
    const payload = await fetchAdmin(
      `/api/admin/wallpapers?${buildWallpaperListParams(state).toString()}`,
      { token: session.session_token },
    );
    renderWallpaperListView(session, payload, state);
  } catch (error) {
    handleAdminError(error);
  }
}

export async function renderWallpaperDetailPage(session, id) {
  setLoadingState("正在读取后台内容详情...");

  try {
    const [detail, tagsPayload] = await Promise.all([
      fetchAdmin(`/api/admin/wallpapers/${encodeURIComponent(id)}`, {
        token: session.session_token,
      }),
      fetchAdmin("/api/admin/tags", {
        token: session.session_token,
      }),
    ]);
    renderWallpaperDetailView(session, detail.data, tagsPayload.data.items || []);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderWallpaperListView(session, payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];
  const pagination = payload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };

  adminRoot.innerHTML = `
    <div class="${TW.panelHead}">
      <div>
        <h2>后台内容列表</h2>
        <p class="${TW.mutedCopy}">支持按内容状态、资源状态、地区和创建时间过滤。</p>
      </div>
      <p class="${TW.metaPill}">第 ${pagination.page} 页 / 共 ${pagination.total_pages || 1} 页</p>
    </div>
    <form class="${TW.form}" id="wallpaper-filter-form">
      <div class="${TW.filterGrid}">
        <div class="${TW.field}">
          <label class="${TW.label}" for="keyword">关键词</label>
          <input class="${TW.input}" id="keyword" name="keyword" type="search" placeholder="标题、说明、版权或标签" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="content-status">内容状态</label>
          <select class="${TW.input}" id="content-status" name="content_status">
            <option value="">全部</option>
            <option value="draft">draft</option>
            <option value="enabled">enabled</option>
            <option value="disabled">disabled</option>
            <option value="deleted">deleted</option>
          </select>
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="image-status">资源状态</label>
          <select class="${TW.input}" id="image-status" name="image_status">
            <option value="">全部</option>
            <option value="pending">pending</option>
            <option value="ready">ready</option>
            <option value="failed">failed</option>
          </select>
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="market-code">地区</label>
          <input class="${TW.input}" id="market-code" name="market_code" type="text" placeholder="例如 en-US" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="created-from">创建开始时间</label>
          <input class="${TW.input}" id="created-from" name="created_from_utc" type="datetime-local" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="created-to">创建结束时间</label>
          <input class="${TW.input}" id="created-to" name="created_to_utc" type="datetime-local" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="page-size">每页数量</label>
          <select class="${TW.input}" id="page-size" name="page_size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </div>
      </div>
      <div class="${TW.btnRow}">
        <button class="${TW.primaryBtn}" type="submit">刷新列表</button>
        <button class="${TW.ghostBtn}" id="reset-wallpaper-filters" type="button">重置筛选</button>
      </div>
    </form>
    <div id="wallpaper-feedback"></div>
    <section class="${TW.tableCard}">
      <div class="${TW.tableWrapper}">
        <table class="${TW.dataTable}">
          <thead>
            <tr>
              <th class="${TW.th}">内容</th>
              <th class="${TW.th}">状态</th>
              <th class="${TW.th}">资源</th>
              <th class="${TW.th}">失败原因</th>
              <th class="${TW.th}">操作</th>
            </tr>
          </thead>
          <tbody id="wallpaper-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="${TW.btnRow}" id="wallpaper-pagination" aria-label="后台内容分页"></nav>
  `;

  const filterForm = document.querySelector("#wallpaper-filter-form");
  const tableBody = document.querySelector("#wallpaper-table-body");
  const feedback = document.querySelector("#wallpaper-feedback");
  const paginationNode = document.querySelector("#wallpaper-pagination");

  if (
    !(filterForm instanceof HTMLFormElement) ||
    !(tableBody instanceof HTMLElement) ||
    !(feedback instanceof HTMLElement) ||
    !(paginationNode instanceof HTMLElement)
  ) {
    return;
  }

  assignFormValue(filterForm, "content_status", state.content_status);
  assignFormValue(filterForm, "image_status", state.image_status);
  assignFormValue(filterForm, "market_code", state.market_code);
  assignFormValue(filterForm, "keyword", state.keyword);
  assignFormValue(filterForm, "created_from_utc", state.created_from_utc);
  assignFormValue(filterForm, "created_to_utc", state.created_to_utc);
  assignFormValue(filterForm, "page_size", state.page_size);

  if (items.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" class="${TW.td}">
          <div class="${TW.notice}">
            <h3>当前没有匹配内容</h3>
            <p>可以调整筛选条件，或先完成采集和资源入库。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    tableBody.innerHTML = items.map((item) => renderWallpaperRow(item)).join("");
  }

  setNotice(feedback, "查询说明", "列表数据来自 /api/admin/wallpapers，危险操作会二次确认并写入审计日志。");
  paginationNode.innerHTML = renderPaginationLinks("/admin/wallpapers", state, pagination.total_pages);

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const nextState = {
      keyword: stringValue(formData.get("keyword")),
      content_status: stringValue(formData.get("content_status")),
      image_status: stringValue(formData.get("image_status")),
      market_code: stringValue(formData.get("market_code")),
      created_from_utc: stringValue(formData.get("created_from_utc")),
      created_to_utc: stringValue(formData.get("created_to_utc")),
      page_size: stringValue(formData.get("page_size")) || "20",
      page: "1",
    };
    redirectTo(`/admin/wallpapers?${buildWallpaperListParams(nextState).toString()}`);
  });

  const resetButton = document.querySelector("#reset-wallpaper-filters");
  if (resetButton instanceof HTMLButtonElement) {
    resetButton.addEventListener("click", () => {
      redirectTo("/admin/wallpapers?page=1&page_size=20");
    });
  }

  bindWallpaperStatusActions(session, feedback);
}

function renderWallpaperDetailView(session, detail, availableTags) {
  const recentOperations = Array.isArray(detail.recent_operations) ? detail.recent_operations : [];
  const currentTags = Array.isArray(detail.tags) ? detail.tags : [];
  const tagOptions = Array.isArray(availableTags) ? availableTags : [];
  const previewUnavailableTitle = "默认资源加载失败";
  const previewUnavailableMessage = detail.preview_url
    ? "当前默认资源地址无法加载，可能是文件缺失、权限异常或上游地址不可达。"
    : "当前没有可展示资源";
  const previewUnavailableLinks = [
    detail.preview_url
      ? `<a class="${TW.inlineLink}" href="${escapeHtml(detail.preview_url)}" target="_blank" rel="noreferrer">打开默认资源地址</a>`
      : "",
    detail.origin_image_url
      ? `<a class="${TW.inlineLink}" href="${escapeHtml(detail.origin_image_url)}" target="_blank" rel="noreferrer">打开来源原图地址</a>`
      : "",
  ]
    .filter(Boolean)
    .join('<span class="text-slate-300">/</span>');
  const previewUnavailableMarkup = `
    <div class="${TW.noticeWarn}">
      <h4>${previewUnavailableTitle}</h4>
      <p>${previewUnavailableMessage}</p>
      ${previewUnavailableLinks ? `<div class="${TW.btnRow}">${previewUnavailableLinks}</div>` : ""}
    </div>
  `;

  adminRoot.innerHTML = `
    <div class="${TW.panelHead}">
      <div>
        <h2>${escapeHtml(detail.title)}</h2>
        <p class="${TW.mutedCopy}">内容详情页通过 <code>/api/admin/wallpapers/${escapeHtml(String(detail.id))}</code> 读取。</p>
      </div>
      <div class="${TW.btnRow}">
        <a class="${TW.ghostBtn}" href="/admin/wallpapers">返回列表</a>
        <a class="${TW.ghostBtn}" href="/admin/audit-logs?target_type=wallpaper&target_id=${escapeHtml(String(detail.id))}">查看审计</a>
      </div>
    </div>
    <div id="detail-feedback"></div>
    <section class="${TW.detailGrid}">
      <article class="${TW.card} media-card">
        <div class="${TW.previewFrame}" data-preview-frame>
          ${
            detail.preview_url
              ? `<img src="${escapeHtml(detail.preview_url)}" alt="${escapeHtml(detail.title)}" data-preview-image />`
              : previewUnavailableMarkup
          }
        </div>
        <div class="${TW.btnRow}">
          ${renderStatusButton(detail.id, "enabled", "启用")}
          ${renderStatusButton(detail.id, "disabled", "禁用")}
          ${renderStatusButton(detail.id, "deleted", "逻辑删除")}
        </div>
      </article>
      <article class="${TW.card}">
        <h3>当前状态</h3>
        <dl class="grid gap-0">
          ${renderDetailRow("内容状态", detail.content_status)}
          ${renderDetailRow("公开展示", detail.is_public ? "是" : "否")}
          ${renderDetailRow("允许下载", detail.is_downloadable ? "是" : "否")}
          ${renderDetailRow("资源快照", detail.resource_status)}
          ${renderDetailRow("资源状态", detail.image_status || "未提供")}
          ${renderDetailRow("失败原因", detail.failure_reason || "无")}
          ${renderDetailRow("逻辑删除时间", detail.deleted_at_utc || "未删除")}
        </dl>
      </article>
      <article class="${TW.card}">
        <h3>展示与来源字段</h3>
        <dl class="grid gap-0">
          ${renderDetailRow("副标题", detail.subtitle || "无")}
          ${renderDetailRow("说明", detail.description || "无")}
          ${renderDetailRow("版权", detail.copyright_text || "无")}
          ${renderDetailRow("地点", detail.location_text || "无")}
          ${renderDetailRow("来源类型", detail.source_type)}
          ${renderDetailRow("来源名称", detail.source_name)}
          ${renderDetailRow("来源键", detail.source_key)}
          ${renderDetailRow("地区", detail.market_code)}
          ${renderDetailRow("壁纸日期", detail.wallpaper_date)}
        </dl>
      </article>
      <article class="${TW.card}">
        <h3>资源信息</h3>
        <dl class="grid gap-0">
          ${renderDetailRow("相对路径", detail.resource_relative_path || "无")}
          ${renderDetailRow("存储后端", detail.storage_backend || "无")}
          ${renderDetailRow("资源类型", detail.resource_type || "无")}
          ${renderDetailRow("MIME 类型", detail.mime_type || "无")}
          ${renderDetailRow("文件大小", formatBytes(detail.file_size_bytes))}
          ${renderDetailRow("尺寸", formatResolution(detail.width, detail.height))}
          ${renderDetailRow("原始页面", detail.origin_page_url || "无")}
          ${renderDetailRow("原始图片", detail.origin_image_url || "无")}
        </dl>
      </article>
      <article class="${TW.card}">
        <div class="${TW.panelHead}">
          <div>
            <h3>标签绑定</h3>
            <p class="${TW.mutedCopy}">这里通过 <code>/api/admin/wallpapers/${escapeHtml(String(detail.id))}/tags</code> 提交绑定关系。</p>
          </div>
          <a class="${TW.inlineLink}" href="/admin/tags">前往标签管理</a>
        </div>
        <div class="${TW.notice}">
          <h4>当前已绑定标签</h4>
          <p>${currentTags.length === 0 ? "当前没有绑定标签。" : currentTags.map((item) => `${item.tag_name} (${item.tag_key})`).join(" / ")}</p>
        </div>
        ${
          tagOptions.length === 0
            ? `<div class="${TW.noticeWarn}"><h4>还没有可维护标签</h4><p>请先去标签管理页创建标签，再回来为内容绑定。</p></div>`
            : `
              <form class="${TW.form}" id="wallpaper-tag-form">
                <div class="${TW.tagChipGrid}">
                  ${tagOptions
                    .map((tag) => {
                      const checked = currentTags.some((item) => Number(item.id) === Number(tag.id));
                      const disabledCopy = tag.status === "disabled" ? "（已停用，仅后台可见）" : "";
                      return `
                        <label class="${TW.tagChip}">
                          <input type="checkbox" name="tag_ids" value="${escapeHtml(String(tag.id))}" ${checked ? "checked" : ""} />
                          <span>
                            <strong>${escapeHtml(tag.tag_name)}</strong>
                            <em>${escapeHtml(tag.tag_key)}${escapeHtml(disabledCopy)}</em>
                          </span>
                        </label>
                      `;
                    })
                    .join("")}
                </div>
                <div class="${TW.field}">
                  <label class="${TW.label}" for="tag-operator-reason">绑定原因</label>
                  <input class="${TW.input}" id="tag-operator-reason" name="operator_reason" type="text" placeholder="例如：补充主题标签" required />
                </div>
                <div class="${TW.btnRow}">
                  <button class="${TW.primaryBtn}" type="submit">保存标签绑定</button>
                </div>
              </form>
            `
        }
      </article>
      <article class="${TW.card} ${TW.cardWide}">
        <h3>最近操作记录</h3>
        ${recentOperations.length === 0 ? `<div class="${TW.notice}"><h4>暂无最近操作</h4><p>该内容尚未产生后台状态变更记录。</p></div>` : renderRecentOperationList(recentOperations)}
      </article>
    </section>
  `;

  const feedback = document.querySelector("#detail-feedback");
  if (!(feedback instanceof HTMLElement)) {
    return;
  }

  bindDetailPreviewFallback({
    frameSelector: "[data-preview-frame]",
    imageSelector: "[data-preview-image]",
    fallbackMarkup: previewUnavailableMarkup,
  });
  bindWallpaperStatusActions(session, feedback);
  bindWallpaperTagActions(session, feedback, detail.id);
}

function bindWallpaperStatusActions(session, feedback) {
  document.querySelectorAll("[data-status-action]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", async () => {
      const targetStatus = button.dataset.statusAction;
      const targetId = button.dataset.wallpaperId;
      if (!targetStatus || !targetId) {
        return;
      }
      const confirmed = window.confirm(`确认把内容 ${targetId} 切换为 ${targetStatus} 吗？`);
      if (!confirmed) {
        return;
      }
      const operatorReason = window.prompt("请输入操作原因", `后台手动切换为 ${targetStatus}`);
      if (!operatorReason) {
        return;
      }
      setNotice(feedback, "正在提交状态切换...", "请求会写入审计日志，请稍候。");
      try {
        await fetchAdmin(`/api/admin/wallpapers/${encodeURIComponent(targetId)}/status`, {
          method: "POST",
          token: session.session_token,
          body: JSON.stringify({
            target_status: targetStatus,
            operator_reason: operatorReason,
          }),
        });
        redirectTo(window.location.pathname + window.location.search);
      } catch (error) {
        console.error(error);
        const message = error instanceof ApiError ? error.message : "状态切换失败，请稍后重试。";
        setNotice(feedback, "操作失败", message);
      }
    });
  });
}

function bindWallpaperTagActions(session, feedback, wallpaperIdValue) {
  const form = document.querySelector("#wallpaper-tag-form");
  if (!(form instanceof HTMLFormElement)) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const selectedIds = formData
      .getAll("tag_ids")
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value) && value > 0);
    const operatorReason = stringValue(formData.get("operator_reason"));
    if (!operatorReason) {
      setNotice(feedback, "缺少原因", "请填写本次标签绑定原因。");
      return;
    }

    setNotice(feedback, "正在保存标签绑定...", "提交后会写入审计日志，并立即影响后台详情与公开筛选。");
    try {
      await fetchAdmin(`/api/admin/wallpapers/${encodeURIComponent(String(wallpaperIdValue))}/tags`, {
        method: "PUT",
        token: session.session_token,
        body: JSON.stringify({
          tag_ids: selectedIds,
          operator_reason: operatorReason,
        }),
      });
      redirectTo(window.location.pathname + window.location.search);
    } catch (error) {
      console.error(error);
      const message = error instanceof ApiError ? error.message : "标签绑定保存失败，请稍后重试。";
      setNotice(feedback, "保存失败", message);
    }
  });
}

function bindDetailPreviewFallback({ frameSelector, imageSelector, fallbackMarkup }) {
  const frame = document.querySelector(frameSelector);
  const image = document.querySelector(imageSelector);
  if (!(frame instanceof HTMLElement) || !(image instanceof HTMLImageElement)) {
    return;
  }

  if (image.complete && image.naturalWidth === 0) {
    frame.innerHTML = fallbackMarkup;
    return;
  }

  image.addEventListener(
    "error",
    () => {
      frame.innerHTML = fallbackMarkup;
    },
    { once: true },
  );
}

function renderWallpaperRow(item) {
  return `
    <tr>
      <td class="${TW.td}">
        <div class="${TW.tableTitle}">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.market_code)} / ${escapeHtml(item.wallpaper_date)}</span>
        </div>
      </td>
      <td class="${TW.td}">
        <div class="${TW.stackedCopy}">
          <span class="${statusBadgeClasses(item.content_status)}">${escapeHtml(item.content_status)}</span>
          <span class="${TW.mutedInline}">公开：${item.is_public ? "是" : "否"}</span>
        </div>
      </td>
      <td class="${TW.td}">
        <div class="${TW.stackedCopy}">
          <span>${escapeHtml(item.resource_status)}</span>
          <span class="${TW.mutedInline}">${escapeHtml(item.image_status || "unknown")}</span>
        </div>
      </td>
      <td class="${TW.td}">${escapeHtml(item.failure_reason || "无")}</td>
      <td class="${TW.td}">
        <div class="${TW.btnRow}">
          <a class="${TW.inlineLink}" href="/admin/wallpapers/${escapeHtml(String(item.id))}">详情</a>
          ${renderStatusButton(item.id, "enabled", "启用")}
          ${renderStatusButton(item.id, "disabled", "禁用")}
          ${renderStatusButton(item.id, "deleted", "删除")}
        </div>
      </td>
    </tr>
  `;
}

function renderRecentOperationList(items) {
  return `
    <div class="${TW.tableWrapper}">
      <table class="${TW.dataTable}">
        <thead>
          <tr>
            <th class="${TW.th}">时间</th>
            <th class="${TW.th}">操作者</th>
            <th class="${TW.th}">动作</th>
            <th class="${TW.th}">trace_id</th>
          </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (item) => `
                <tr>
                  <td class="${TW.td}">${escapeHtml(item.created_at_utc)}</td>
                  <td class="${TW.td}">${escapeHtml(item.admin_username)}</td>
                  <td class="${TW.td}">${escapeHtml(item.action_type)}</td>
                  <td class="${TW.td}"><code>${escapeHtml(item.trace_id)}</code></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderStatusButton(wallpaperIdValue, targetStatus, label) {
  return `<button class="${TW.miniBtn}" type="button" data-wallpaper-id="${escapeHtml(String(wallpaperIdValue))}" data-status-action="${escapeHtml(targetStatus)}">${escapeHtml(label)}</button>`;
}
