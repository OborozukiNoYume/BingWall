const adminRoot = document.querySelector("#admin-root");
const body = document.body;
const pageName = body.dataset.page;
const wallpaperId = body.dataset.wallpaperId;
const sessionCopyNode = document.querySelector("[data-admin-session]");
const logoutButton = document.querySelector("[data-admin-logout]");
const SESSION_STORAGE_KEY = "bingwall_admin_session";

document.addEventListener("DOMContentLoaded", async () => {
  bindLogoutButton();

  if (!(adminRoot instanceof HTMLElement)) {
    return;
  }

  if (pageName === "admin-login") {
    renderLoginPage();
    const session = loadSession();
    if (session) {
      updateSessionCopy(`当前已保存后台会话，账号：${session.username}`);
    } else {
      updateSessionCopy("当前未登录后台。");
    }
    return;
  }

  const session = loadSession();
  if (!session) {
    redirectToLogin();
    return;
  }

  updateSessionCopy(`当前管理员：${session.username}，会话到期时间：${session.expires_at_utc}`);

  if (pageName === "admin-wallpapers") {
    await renderWallpaperListPage(session);
    return;
  }

  if (pageName === "admin-detail" && wallpaperId) {
    await renderWallpaperDetailPage(session, wallpaperId);
    return;
  }

  if (pageName === "admin-audit") {
    await renderAuditPage(session);
  }
});

function bindLogoutButton() {
  if (!(logoutButton instanceof HTMLButtonElement)) {
    return;
  }
  logoutButton.addEventListener("click", async () => {
    const session = loadSession();
    clearSession();
    if (session) {
      try {
        await fetchAdmin("/api/admin/auth/logout", {
          method: "POST",
          token: session.session_token,
        });
      } catch (error) {
        console.error(error);
      }
    }
    redirectToLogin();
  });
}

function renderLoginPage() {
  adminRoot.innerHTML = `
    <section class="auth-card">
      <div>
        <p class="admin-eyebrow">后台认证</p>
        <h2>登录后再进行内容管理</h2>
        <p class="muted-copy">登录成功后，浏览器只保存会话令牌；后台页面不会直接读取数据库文件。</p>
      </div>
      <form class="admin-form" id="admin-login-form">
        <div class="field-group">
          <label for="username">用户名</label>
          <input id="username" name="username" type="text" autocomplete="username" required />
        </div>
        <div class="field-group">
          <label for="password">密码</label>
          <input id="password" name="password" type="password" autocomplete="current-password" required />
        </div>
        <div class="button-row">
          <button class="primary-button" type="submit">登录后台</button>
        </div>
      </form>
      <div class="notice-card" id="login-feedback">
        <h3>说明</h3>
        <p>默认通过 <code>/api/admin/auth/login</code> 创建会话。</p>
      </div>
    </section>
  `;

  const form = document.querySelector("#admin-login-form");
  const feedback = document.querySelector("#login-feedback");
  if (!(form instanceof HTMLFormElement) || !(feedback instanceof HTMLElement)) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    setNotice(feedback, "正在登录后台...", "请稍候，系统会校验账号和密码。");

    try {
      const response = await fetchAdmin("/api/admin/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: stringValue(formData.get("username")),
          password: stringValue(formData.get("password")),
        }),
      });
      storeSession(response);
      redirectTo("/admin/wallpapers");
    } catch (error) {
      console.error(error);
      const message = error instanceof ApiError ? error.message : "后台登录失败，请稍后重试。";
      setNotice(feedback, "登录失败", message);
    }
  });
}

async function renderWallpaperListPage(session) {
  setLoadingState("正在读取后台内容列表...");

  try {
    const state = readWallpaperListState();
    const payload = await fetchAdmin(
      `/api/admin/wallpapers?${buildWallpaperListParams(state).toString()}`,
      {
        token: session.session_token,
      },
    );
    renderWallpaperListView(session, payload, state);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderWallpaperListView(session, payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];
  const pagination = payload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>后台内容列表</h2>
        <p class="muted-copy">支持按内容状态、资源状态、地区和创建时间过滤。</p>
      </div>
      <p class="meta-pill">第 ${pagination.page} 页 / 共 ${pagination.total_pages || 1} 页</p>
    </div>
    <form class="admin-form" id="wallpaper-filter-form">
      <div class="filter-grid">
        <div class="field-group">
          <label for="content-status">内容状态</label>
          <select id="content-status" name="content_status">
            <option value="">全部</option>
            <option value="draft">draft</option>
            <option value="enabled">enabled</option>
            <option value="disabled">disabled</option>
            <option value="deleted">deleted</option>
          </select>
        </div>
        <div class="field-group">
          <label for="image-status">资源状态</label>
          <select id="image-status" name="image_status">
            <option value="">全部</option>
            <option value="pending">pending</option>
            <option value="ready">ready</option>
            <option value="failed">failed</option>
          </select>
        </div>
        <div class="field-group">
          <label for="market-code">地区</label>
          <input id="market-code" name="market_code" type="text" placeholder="例如 en-US" />
        </div>
        <div class="field-group">
          <label for="created-from">创建开始时间</label>
          <input id="created-from" name="created_from_utc" type="datetime-local" />
        </div>
        <div class="field-group">
          <label for="created-to">创建结束时间</label>
          <input id="created-to" name="created_to_utc" type="datetime-local" />
        </div>
        <div class="field-group">
          <label for="page-size">每页数量</label>
          <select id="page-size" name="page_size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </div>
      </div>
      <div class="button-row">
        <button class="primary-button" type="submit">刷新列表</button>
        <button class="ghost-button" id="reset-wallpaper-filters" type="button">重置筛选</button>
      </div>
    </form>
    <div id="wallpaper-feedback"></div>
    <section class="table-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>内容</th>
              <th>状态</th>
              <th>资源</th>
              <th>失败原因</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody id="wallpaper-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="button-row" id="wallpaper-pagination" aria-label="后台内容分页"></nav>
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
  assignFormValue(filterForm, "created_from_utc", state.created_from_utc);
  assignFormValue(filterForm, "created_to_utc", state.created_to_utc);
  assignFormValue(filterForm, "page_size", state.page_size);

  if (items.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5">
          <div class="notice-card">
            <h3>当前没有匹配内容</h3>
            <p>可以调整筛选条件，或先完成采集和资源入库。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    tableBody.innerHTML = items.map((item) => renderWallpaperRow(item)).join("");
  }

  setNotice(
    feedback,
    "查询说明",
    "列表数据来自 /api/admin/wallpapers，危险操作会二次确认并写入审计日志。",
  );
  paginationNode.innerHTML = renderPaginationLinks("/admin/wallpapers", state, pagination.total_pages);

  filterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const nextState = {
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

  tableBody.querySelectorAll("[data-status-action]").forEach((button) => {
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

async function renderWallpaperDetailPage(session, id) {
  setLoadingState("正在读取后台内容详情...");

  try {
    const detail = await fetchAdmin(`/api/admin/wallpapers/${encodeURIComponent(id)}`, {
      token: session.session_token,
    });
    renderWallpaperDetailView(session, detail.data);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderWallpaperDetailView(session, detail) {
  const recentOperations = Array.isArray(detail.recent_operations) ? detail.recent_operations : [];

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>${escapeHtml(detail.title)}</h2>
        <p class="muted-copy">内容详情页通过 <code>/api/admin/wallpapers/${escapeHtml(String(detail.id))}</code> 读取。</p>
      </div>
      <div class="button-row">
        <a class="ghost-button" href="/admin/wallpapers">返回列表</a>
        <a class="ghost-button" href="/admin/audit-logs?target_type=wallpaper&target_id=${escapeHtml(String(detail.id))}">查看审计</a>
      </div>
    </div>
    <div id="detail-feedback"></div>
    <section class="detail-grid">
      <article class="detail-card media-card">
        <div class="preview-frame">
          ${detail.preview_url ? `<img src="${escapeHtml(detail.preview_url)}" alt="${escapeHtml(detail.title)}" />` : `<div class="empty-preview">当前没有可展示资源</div>`}
        </div>
        <div class="button-row">
          ${renderStatusButton(detail.id, "enabled", "启用")}
          ${renderStatusButton(detail.id, "disabled", "禁用")}
          ${renderStatusButton(detail.id, "deleted", "逻辑删除")}
        </div>
      </article>
      <article class="detail-card">
        <h3>当前状态</h3>
        <dl class="detail-list">
          ${renderDetailRow("内容状态", detail.content_status)}
          ${renderDetailRow("公开展示", detail.is_public ? "是" : "否")}
          ${renderDetailRow("允许下载", detail.is_downloadable ? "是" : "否")}
          ${renderDetailRow("资源快照", detail.resource_status)}
          ${renderDetailRow("资源状态", detail.image_status || "未提供")}
          ${renderDetailRow("失败原因", detail.failure_reason || "无")}
          ${renderDetailRow("逻辑删除时间", detail.deleted_at_utc || "未删除")}
        </dl>
      </article>
      <article class="detail-card">
        <h3>展示与来源字段</h3>
        <dl class="detail-list">
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
      <article class="detail-card">
        <h3>资源信息</h3>
        <dl class="detail-list">
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
      <article class="detail-card detail-card-wide">
        <h3>最近操作记录</h3>
        ${recentOperations.length === 0 ? `<div class="notice-card"><h4>暂无最近操作</h4><p>该内容尚未产生后台状态变更记录。</p></div>` : renderRecentOperationList(recentOperations)}
      </article>
    </section>
  `;

  const feedback = document.querySelector("#detail-feedback");
  if (!(feedback instanceof HTMLElement)) {
    return;
  }

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
      const confirmed = window.confirm(`确认执行 ${targetStatus} 吗？`);
      if (!confirmed) {
        return;
      }
      const operatorReason = window.prompt("请输入操作原因", `详情页执行 ${targetStatus}`);
      if (!operatorReason) {
        return;
      }
      setNotice(feedback, "正在提交状态切换...", "请求会记录操作者、目标对象和 trace_id。");
      try {
        await fetchAdmin(`/api/admin/wallpapers/${encodeURIComponent(targetId)}/status`, {
          method: "POST",
          token: session.session_token,
          body: JSON.stringify({
            target_status: targetStatus,
            operator_reason: operatorReason,
          }),
        });
        redirectTo(`/admin/wallpapers/${encodeURIComponent(targetId)}`);
      } catch (error) {
        console.error(error);
        const message = error instanceof ApiError ? error.message : "状态切换失败，请稍后重试。";
        setNotice(feedback, "操作失败", message);
      }
    });
  });
}

async function renderAuditPage(session) {
  setLoadingState("正在读取后台审计记录...");

  try {
    const state = readAuditState();
    const payload = await fetchAdmin(`/api/admin/audit-logs?${buildAuditParams(state).toString()}`, {
      token: session.session_token,
    });
    renderAuditView(payload, state);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderAuditView(payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];
  const pagination = payload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>后台审计记录</h2>
        <p class="muted-copy">支持按操作者、目标对象和时间范围查询。</p>
      </div>
      <p class="meta-pill">共 ${pagination.total} 条</p>
    </div>
    <form class="admin-form" id="audit-filter-form">
      <div class="filter-grid">
        <div class="field-group">
          <label for="admin-user-id">管理员 ID</label>
          <input id="admin-user-id" name="admin_user_id" type="number" min="1" />
        </div>
        <div class="field-group">
          <label for="target-type">目标类型</label>
          <select id="target-type" name="target_type">
            <option value="">全部</option>
            <option value="wallpaper">wallpaper</option>
            <option value="admin_session">admin_session</option>
          </select>
        </div>
        <div class="field-group">
          <label for="target-id">目标 ID</label>
          <input id="target-id" name="target_id" type="text" />
        </div>
        <div class="field-group">
          <label for="started-from">开始时间</label>
          <input id="started-from" name="started_from_utc" type="datetime-local" />
        </div>
        <div class="field-group">
          <label for="started-to">结束时间</label>
          <input id="started-to" name="started_to_utc" type="datetime-local" />
        </div>
        <div class="field-group">
          <label for="audit-page-size">每页数量</label>
          <select id="audit-page-size" name="page_size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </div>
      </div>
      <div class="button-row">
        <button class="primary-button" type="submit">刷新审计记录</button>
        <button class="ghost-button" id="reset-audit-filters" type="button">重置筛选</button>
      </div>
    </form>
    <section class="table-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者</th>
              <th>动作</th>
              <th>目标</th>
              <th>trace_id</th>
              <th>状态快照</th>
            </tr>
          </thead>
          <tbody id="audit-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="button-row" id="audit-pagination" aria-label="后台审计分页"></nav>
  `;

  const filterForm = document.querySelector("#audit-filter-form");
  const tableBody = document.querySelector("#audit-table-body");
  const paginationNode = document.querySelector("#audit-pagination");

  if (
    !(filterForm instanceof HTMLFormElement) ||
    !(tableBody instanceof HTMLElement) ||
    !(paginationNode instanceof HTMLElement)
  ) {
    return;
  }

  assignFormValue(filterForm, "admin_user_id", state.admin_user_id);
  assignFormValue(filterForm, "target_type", state.target_type);
  assignFormValue(filterForm, "target_id", state.target_id);
  assignFormValue(filterForm, "started_from_utc", state.started_from_utc);
  assignFormValue(filterForm, "started_to_utc", state.started_to_utc);
  assignFormValue(filterForm, "page_size", state.page_size);

  if (items.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="notice-card">
            <h3>当前没有匹配审计记录</h3>
            <p>可以调整对象 ID 或时间范围后再试。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    tableBody.innerHTML = items.map((item) => renderAuditRow(item)).join("");
  }

  paginationNode.innerHTML = renderPaginationLinks("/admin/audit-logs", state, pagination.total_pages);

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const nextState = {
      admin_user_id: stringValue(formData.get("admin_user_id")),
      target_type: stringValue(formData.get("target_type")),
      target_id: stringValue(formData.get("target_id")),
      started_from_utc: stringValue(formData.get("started_from_utc")),
      started_to_utc: stringValue(formData.get("started_to_utc")),
      page_size: stringValue(formData.get("page_size")) || "20",
      page: "1",
    };
    redirectTo(`/admin/audit-logs?${buildAuditParams(nextState).toString()}`);
  });

  const resetButton = document.querySelector("#reset-audit-filters");
  if (resetButton instanceof HTMLButtonElement) {
    resetButton.addEventListener("click", () => {
      redirectTo("/admin/audit-logs?page=1&page_size=20");
    });
  }
}

function renderWallpaperRow(item) {
  return `
    <tr>
      <td>
        <div class="table-title">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.market_code)} / ${escapeHtml(item.wallpaper_date)}</span>
        </div>
      </td>
      <td>
        <div class="stacked-copy">
          <span class="status-badge">${escapeHtml(item.content_status)}</span>
          <span class="muted-inline">公开：${item.is_public ? "是" : "否"}</span>
        </div>
      </td>
      <td>
        <div class="stacked-copy">
          <span>${escapeHtml(item.resource_status)}</span>
          <span class="muted-inline">${escapeHtml(item.image_status || "unknown")}</span>
        </div>
      </td>
      <td>${escapeHtml(item.failure_reason || "无")}</td>
      <td>
        <div class="button-row">
          <a class="inline-link" href="/admin/wallpapers/${escapeHtml(String(item.id))}">详情</a>
          ${renderStatusButton(item.id, "enabled", "启用")}
          ${renderStatusButton(item.id, "disabled", "禁用")}
          ${renderStatusButton(item.id, "deleted", "删除")}
        </div>
      </td>
    </tr>
  `;
}

function renderStatusButton(wallpaperId, targetStatus, label) {
  return `<button class="mini-button" type="button" data-wallpaper-id="${escapeHtml(String(wallpaperId))}" data-status-action="${escapeHtml(targetStatus)}">${escapeHtml(label)}</button>`;
}

function renderAuditRow(item) {
  return `
    <tr>
      <td>${escapeHtml(item.created_at_utc)}</td>
      <td>${escapeHtml(item.admin_username)} (#${escapeHtml(String(item.admin_user_id))})</td>
      <td>${escapeHtml(item.action_type)}</td>
      <td>${escapeHtml(item.target_type)} / ${escapeHtml(item.target_id)}</td>
      <td><code>${escapeHtml(item.trace_id)}</code></td>
      <td><pre>${escapeHtml(JSON.stringify({ before: item.before_state, after: item.after_state }, null, 2))}</pre></td>
    </tr>
  `;
}

function renderRecentOperationList(items) {
  return `
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>操作者</th>
            <th>动作</th>
            <th>trace_id</th>
          </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (item) => `
                <tr>
                  <td>${escapeHtml(item.created_at_utc)}</td>
                  <td>${escapeHtml(item.admin_username)}</td>
                  <td>${escapeHtml(item.action_type)}</td>
                  <td><code>${escapeHtml(item.trace_id)}</code></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderDetailRow(label, value) {
  return `
    <div>
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(value)}</dd>
    </div>
  `;
}

function renderPaginationLinks(basePath, state, totalPages) {
  if (!totalPages || totalPages <= 1) {
    return "";
  }

  const currentPage = Number(state.page || "1");
  const links = [];
  if (currentPage > 1) {
    links.push(`<a class="ghost-button" href="${buildPageHref(basePath, state, currentPage - 1)}">上一页</a>`);
  }
  if (currentPage < totalPages) {
    links.push(`<a class="ghost-button" href="${buildPageHref(basePath, state, currentPage + 1)}">下一页</a>`);
  }
  return links.join("");
}

function buildPageHref(basePath, state, page) {
  const nextState = { ...state, page: String(page) };
  const params = basePath.includes("audit") ? buildAuditParams(nextState) : buildWallpaperListParams(nextState);
  return `${basePath}?${params.toString()}`;
}

function readWallpaperListState() {
  const params = new URLSearchParams(window.location.search);
  return {
    content_status: params.get("content_status") || "",
    image_status: params.get("image_status") || "",
    market_code: params.get("market_code") || "",
    created_from_utc: toDatetimeLocalValue(params.get("created_from_utc")),
    created_to_utc: toDatetimeLocalValue(params.get("created_to_utc")),
    page: params.get("page") || "1",
    page_size: params.get("page_size") || "20",
  };
}

function readAuditState() {
  const params = new URLSearchParams(window.location.search);
  return {
    admin_user_id: params.get("admin_user_id") || "",
    target_type: params.get("target_type") || "",
    target_id: params.get("target_id") || "",
    started_from_utc: toDatetimeLocalValue(params.get("started_from_utc")),
    started_to_utc: toDatetimeLocalValue(params.get("started_to_utc")),
    page: params.get("page") || "1",
    page_size: params.get("page_size") || "20",
  };
}

function buildWallpaperListParams(state) {
  const params = new URLSearchParams();
  params.set("page", state.page || "1");
  params.set("page_size", state.page_size || "20");
  setOptionalParam(params, "content_status", state.content_status);
  setOptionalParam(params, "image_status", state.image_status);
  setOptionalParam(params, "market_code", state.market_code);
  setOptionalParam(params, "created_from_utc", toUtcQueryValue(state.created_from_utc));
  setOptionalParam(params, "created_to_utc", toUtcQueryValue(state.created_to_utc));
  return params;
}

function buildAuditParams(state) {
  const params = new URLSearchParams();
  params.set("page", state.page || "1");
  params.set("page_size", state.page_size || "20");
  setOptionalParam(params, "admin_user_id", state.admin_user_id);
  setOptionalParam(params, "target_type", state.target_type);
  setOptionalParam(params, "target_id", state.target_id);
  setOptionalParam(params, "started_from_utc", toUtcQueryValue(state.started_from_utc));
  setOptionalParam(params, "started_to_utc", toUtcQueryValue(state.started_to_utc));
  return params;
}

function setOptionalParam(params, key, value) {
  if (value) {
    params.set(key, value);
  }
}

function assignFormValue(form, name, value) {
  const field = form.elements.namedItem(name);
  if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement) {
    field.value = value || "";
  }
}

function setLoadingState(message) {
  adminRoot.innerHTML = `
    <div class="notice-card">
      <h2>正在加载</h2>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
}

function setNotice(node, title, copy) {
  node.innerHTML = `
    <div class="notice-card">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(copy)}</p>
    </div>
  `;
}

function handleAdminError(error) {
  console.error(error);
  if (error instanceof ApiError && error.status === 401) {
    clearSession();
    redirectToLogin();
    return;
  }
  const message = error instanceof ApiError ? error.message : "后台接口暂时不可用，请稍后重试。";
  adminRoot.innerHTML = `
    <div class="notice-card notice-card-warning">
      <h2>服务繁忙</h2>
      <p>${escapeHtml(message)}</p>
      <div class="button-row">
        <a class="ghost-button" href="/admin/wallpapers">返回内容管理</a>
      </div>
    </div>
  `;
}

async function fetchAdmin(url, options = {}) {
  const headers = { Accept: "application/json" };
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(url, {
    method: options.method || "GET",
    headers,
    body: options.body,
  });
  const payload = await response.json();
  if (!response.ok || payload.success !== true) {
    throw new ApiError(response.status, payload.message || "后台接口请求失败");
  }
  return payload.data ? { ...payload, ...payload.data } : payload;
}

function loadSession() {
  const rawValue = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }
  try {
    return JSON.parse(rawValue);
  } catch {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

function storeSession(response) {
  const session = {
    session_token: response.session_token,
    expires_at_utc: response.expires_at_utc,
    username: response.user.username,
    role_name: response.user.role_name,
  };
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

function clearSession() {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
  updateSessionCopy("当前未登录后台。");
}

function updateSessionCopy(message) {
  if (sessionCopyNode instanceof HTMLElement) {
    sessionCopyNode.textContent = message;
  }
}

function redirectToLogin() {
  redirectTo("/admin/login");
}

function redirectTo(url) {
  window.location.assign(url);
}

function stringValue(value) {
  return typeof value === "string" ? value.trim() : "";
}

function formatResolution(width, height) {
  if (!width || !height) {
    return "未提供";
  }
  return `${width} x ${height}`;
}

function formatBytes(value) {
  if (!value) {
    return "未提供";
  }
  return `${value} bytes`;
}

function toDatetimeLocalValue(value) {
  if (!value) {
    return "";
  }
  return String(value).replace("Z", "").slice(0, 16);
}

function toUtcQueryValue(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toISOString().replace(".000Z", "Z");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
