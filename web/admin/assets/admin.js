const adminRoot = document.querySelector("#admin-root");
const body = document.body;
const pageName = body.dataset.page;
const wallpaperId = body.dataset.wallpaperId;
const taskId = body.dataset.taskId;
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

  if (pageName === "admin-tasks") {
    await renderTaskListPage(session);
    return;
  }

  if (pageName === "admin-download-stats") {
    await renderDownloadStatsPage(session);
    return;
  }

  if (pageName === "admin-tags") {
    await renderTagManagementPage(session);
    return;
  }

  if (pageName === "admin-change-password") {
    renderChangePasswordPage(session);
    return;
  }

  if (pageName === "admin-task-detail" && taskId) {
    await renderTaskDetailPage(session, taskId);
    return;
  }

  if (pageName === "admin-logs") {
    await renderLogPage(session);
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

function renderChangePasswordPage(session) {
  adminRoot.innerHTML = `
    <section class="auth-card">
      <div>
        <p class="admin-eyebrow">账号安全</p>
        <h2>修改后台密码</h2>
        <p class="muted-copy">提交成功后，当前账号的后台会话会立即失效，需使用新密码重新登录。</p>
      </div>
      <form class="admin-form" id="admin-change-password-form">
        <div class="field-group">
          <label for="current-password">当前密码</label>
          <input
            id="current-password"
            name="current_password"
            type="password"
            autocomplete="current-password"
            required
          />
        </div>
        <div class="field-group">
          <label for="new-password">新密码</label>
          <input
            id="new-password"
            name="new_password"
            type="password"
            autocomplete="new-password"
            required
          />
        </div>
        <div class="field-group">
          <label for="confirm-new-password">确认新密码</label>
          <input
            id="confirm-new-password"
            name="confirm_new_password"
            type="password"
            autocomplete="new-password"
            required
          />
        </div>
        <div class="button-row">
          <button class="primary-button" type="submit">保存新密码</button>
          <a class="ghost-button" href="/admin/wallpapers">返回内容管理</a>
        </div>
      </form>
      <div class="notice-card" id="change-password-feedback">
        <h3>说明</h3>
        <p>当前页面通过 <code>/api/admin/auth/change-password</code> 校验当前密码并更新后台口令。</p>
      </div>
    </section>
  `;

  const form = document.querySelector("#admin-change-password-form");
  const feedback = document.querySelector("#change-password-feedback");
  if (!(form instanceof HTMLFormElement) || !(feedback instanceof HTMLElement)) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const currentPassword = stringValue(formData.get("current_password"));
    const newPassword = stringValue(formData.get("new_password"));
    const confirmNewPassword = stringValue(formData.get("confirm_new_password"));

    if (newPassword !== confirmNewPassword) {
      setNotice(feedback, "提交失败", "两次输入的新密码不一致，请重新确认。");
      return;
    }

    setNotice(feedback, "正在修改密码...", "系统会校验当前密码，并在成功后要求重新登录。");

    try {
      const response = await fetchAdmin("/api/admin/auth/change-password", {
        method: "POST",
        token: session.session_token,
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          confirm_new_password: confirmNewPassword,
        }),
      });
      clearSession();
      setNotice(
        feedback,
        "密码已修改",
        `已使 ${response.revoked_session_count} 个后台会话失效，正在返回登录页。`,
      );
      window.setTimeout(() => {
        redirectToLogin();
      }, 1200);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        handleAdminError(error);
        return;
      }
      console.error(error);
      const message = error instanceof ApiError ? error.message : "修改密码失败，请稍后重试。";
      setNotice(feedback, "修改失败", message);
    }
  });
}

async function renderWallpaperListPage(session) {
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
          <label for="keyword">关键词</label>
          <input id="keyword" name="keyword" type="search" placeholder="标题、说明、版权或标签" />
        </div>
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
  assignFormValue(filterForm, "keyword", state.keyword);
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

async function renderWallpaperDetailPage(session, id) {
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

function renderWallpaperDetailView(session, detail, availableTags) {
  const recentOperations = Array.isArray(detail.recent_operations) ? detail.recent_operations : [];
  const currentTags = Array.isArray(detail.tags) ? detail.tags : [];
  const tagOptions = Array.isArray(availableTags) ? availableTags : [];

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
      <article class="detail-card">
        <div class="panel-head">
          <div>
            <h3>标签绑定</h3>
            <p class="muted-copy">这里通过 <code>/api/admin/wallpapers/${escapeHtml(String(detail.id))}/tags</code> 提交绑定关系。</p>
          </div>
          <a class="inline-link" href="/admin/tags">前往标签管理</a>
        </div>
        <div class="notice-card">
          <h4>当前已绑定标签</h4>
          <p>${currentTags.length === 0 ? "当前没有绑定标签。" : currentTags.map((item) => `${item.tag_name} (${item.tag_key})`).join(" / ")}</p>
        </div>
        ${
          tagOptions.length === 0
            ? `<div class="notice-card notice-card-warning"><h4>还没有可维护标签</h4><p>请先去标签管理页创建标签，再回来为内容绑定。</p></div>`
            : `
              <form class="admin-form" id="wallpaper-tag-form">
                <div class="tag-chip-grid">
                  ${tagOptions
                    .map((tag) => {
                      const checked = currentTags.some((item) => Number(item.id) === Number(tag.id));
                      const disabledCopy = tag.status === "disabled" ? "（已停用，仅后台可见）" : "";
                      return `
                        <label class="tag-chip">
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
                <div class="field-group">
                  <label for="tag-operator-reason">绑定原因</label>
                  <input id="tag-operator-reason" name="operator_reason" type="text" placeholder="例如：补充主题标签" required />
                </div>
                <div class="button-row">
                  <button class="primary-button" type="submit">保存标签绑定</button>
                </div>
              </form>
            `
        }
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

  bindWallpaperStatusActions(session, feedback);
  bindWallpaperTagActions(session, feedback, detail.id);
}

async function renderTagManagementPage(session) {
  setLoadingState("正在读取标签列表...");

  try {
    const state = readTagState();
    const payload = await fetchAdmin(`/api/admin/tags?${buildTagParams(state).toString()}`, {
      token: session.session_token,
    });
    renderTagManagementView(session, payload, state);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderTagManagementView(session, payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>标签维护</h2>
        <p class="muted-copy">标签定义统一保存在 <code>tags</code> 表中，内容绑定保存在 <code>wallpaper_tags</code> 表中。</p>
      </div>
      <p class="meta-pill">共 ${items.length} 个标签</p>
    </div>
    <section class="detail-grid">
      <article class="detail-card">
        <h3>创建 / 更新标签</h3>
        <form class="admin-form" id="tag-form">
          <input type="hidden" name="tag_id" />
          <div class="filter-grid">
            <div class="field-group">
              <label for="tag-key">稳定键</label>
              <input id="tag-key" name="tag_key" type="text" placeholder="例如 theme_landscape" required />
            </div>
            <div class="field-group">
              <label for="tag-name">标签名</label>
              <input id="tag-name" name="tag_name" type="text" placeholder="例如 风景" required />
            </div>
            <div class="field-group">
              <label for="tag-category">分类</label>
              <input id="tag-category" name="tag_category" type="text" placeholder="例如 theme" />
            </div>
            <div class="field-group">
              <label for="tag-status">状态</label>
              <select id="tag-status" name="status">
                <option value="enabled">enabled</option>
                <option value="disabled">disabled</option>
              </select>
            </div>
            <div class="field-group">
              <label for="tag-sort-weight">排序权重</label>
              <input id="tag-sort-weight" name="sort_weight" type="number" value="0" />
            </div>
            <div class="field-group">
              <label for="tag-operator-reason">操作原因</label>
              <input id="tag-operator-reason" name="operator_reason" type="text" placeholder="例如：新增公开主题标签" required />
            </div>
          </div>
          <div class="button-row">
            <button class="primary-button" type="submit">保存标签</button>
            <button class="ghost-button" id="reset-tag-form" type="button">清空表单</button>
          </div>
        </form>
        <div id="tag-form-feedback"></div>
      </article>
      <article class="detail-card">
        <h3>标签筛选</h3>
        <form class="admin-form" id="tag-filter-form">
          <div class="filter-grid">
            <div class="field-group">
              <label for="tag-filter-status">状态</label>
              <select id="tag-filter-status" name="status">
                <option value="">全部</option>
                <option value="enabled">enabled</option>
                <option value="disabled">disabled</option>
              </select>
            </div>
            <div class="field-group">
              <label for="tag-filter-category">分类</label>
              <input id="tag-filter-category" name="tag_category" type="text" placeholder="例如 theme" />
            </div>
          </div>
          <div class="button-row">
            <button class="primary-button" type="submit">刷新标签列表</button>
            <button class="ghost-button" id="reset-tag-filters" type="button">重置筛选</button>
          </div>
        </form>
      </article>
    </section>
    <section class="table-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>标签</th>
              <th>状态</th>
              <th>分类</th>
              <th>排序</th>
              <th>内容数</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody id="tag-table-body"></tbody>
        </table>
      </div>
    </section>
  `;

  const form = document.querySelector("#tag-form");
  const feedback = document.querySelector("#tag-form-feedback");
  const filterForm = document.querySelector("#tag-filter-form");
  const tableBody = document.querySelector("#tag-table-body");

  if (
    !(form instanceof HTMLFormElement) ||
    !(feedback instanceof HTMLElement) ||
    !(filterForm instanceof HTMLFormElement) ||
    !(tableBody instanceof HTMLElement)
  ) {
    return;
  }

  assignFormValue(filterForm, "status", state.status);
  assignFormValue(filterForm, "tag_category", state.tag_category);

  if (items.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="notice-card">
            <h3>当前没有匹配标签</h3>
            <p>可以先创建标签，或者调整状态与分类筛选条件。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    tableBody.innerHTML = items.map((item) => renderTagRow(item)).join("");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const tagId = stringValue(formData.get("tag_id"));
    const isUpdate = Boolean(tagId);
    const requestPayload = {
      tag_key: stringValue(formData.get("tag_key")),
      tag_name: stringValue(formData.get("tag_name")),
      tag_category: stringValue(formData.get("tag_category")) || null,
      status: stringValue(formData.get("status")) || "enabled",
      sort_weight: Number(formData.get("sort_weight") || 0),
      operator_reason: stringValue(formData.get("operator_reason")),
    };

    setNotice(feedback, isUpdate ? "正在更新标签..." : "正在创建标签...", "操作会写入审计日志，请稍候。");
    try {
      if (isUpdate) {
        await fetchAdmin(`/api/admin/tags/${encodeURIComponent(tagId)}`, {
          method: "PATCH",
          token: session.session_token,
          body: JSON.stringify(requestPayload),
        });
      } else {
        await fetchAdmin("/api/admin/tags", {
          method: "POST",
          token: session.session_token,
          body: JSON.stringify(requestPayload),
        });
      }
      redirectTo(`/admin/tags?${buildTagParams(state).toString()}`);
    } catch (error) {
      console.error(error);
      const message = error instanceof ApiError ? error.message : "标签保存失败，请稍后重试。";
      setNotice(feedback, "操作失败", message);
    }
  });

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const nextState = {
      status: stringValue(formData.get("status")),
      tag_category: stringValue(formData.get("tag_category")),
    };
    redirectTo(`/admin/tags?${buildTagParams(nextState).toString()}`);
  });

  const resetFormButton = document.querySelector("#reset-tag-form");
  if (resetFormButton instanceof HTMLButtonElement) {
    resetFormButton.addEventListener("click", () => {
      form.reset();
      assignFormValue(form, "tag_id", "");
      assignFormValue(form, "sort_weight", "0");
    });
  }

  const resetFilterButton = document.querySelector("#reset-tag-filters");
  if (resetFilterButton instanceof HTMLButtonElement) {
    resetFilterButton.addEventListener("click", () => {
      redirectTo("/admin/tags");
    });
  }

  bindTagEditActions(items);
}

async function renderTaskListPage(session) {
  setLoadingState("正在读取后台采集任务...");

  try {
    const state = readTaskListState();
    const payload = await fetchAdmin(
      `/api/admin/collection-tasks?${buildTaskParams(state).toString()}`,
      { token: session.session_token },
    );
    renderTaskListView(session, payload, state);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderTaskListView(session, payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];
  const pagination = payload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>采集任务与后台观测</h2>
        <p class="muted-copy">手动创建任务后，可由 cron 自动消费，也可在本页对 queued 任务执行一次人工触发。</p>
      </div>
      <p class="meta-pill">共 ${pagination.total} 条任务</p>
    </div>
    <section class="detail-grid">
      <article class="detail-card">
        <h3>创建手动采集任务</h3>
        <form class="admin-form" id="task-create-form">
          <div class="filter-grid">
            <div class="field-group">
              <label for="task-source-type">来源类型</label>
              <select id="task-source-type" name="source_type">
                <option value="bing">bing</option>
                <option value="nasa_apod">nasa_apod</option>
              </select>
            </div>
            <div class="field-group">
              <label for="task-market-code">地区</label>
              <input id="task-market-code" name="market_code" type="text" value="en-US" required />
            </div>
            <div class="field-group">
              <label for="task-date-from">开始日期</label>
              <input id="task-date-from" name="date_from" type="date" required />
            </div>
            <div class="field-group">
              <label for="task-date-to">结束日期</label>
              <input id="task-date-to" name="date_to" type="date" required />
            </div>
          </div>
          <label class="checkbox-row">
            <input id="task-force-refresh" name="force_refresh" type="checkbox" />
            <span>记录 force_refresh 请求参数</span>
          </label>
          <div class="button-row">
            <button class="primary-button" type="submit">创建 queued 任务</button>
          </div>
        </form>
        <div id="task-create-feedback"></div>
      </article>
      <article class="detail-card">
        <h3>任务筛选</h3>
        <form class="admin-form" id="task-filter-form">
          <div class="filter-grid">
            <div class="field-group">
              <label for="task-status-filter">任务状态</label>
              <select id="task-status-filter" name="task_status">
                <option value="">全部</option>
                <option value="queued">queued</option>
                <option value="running">running</option>
                <option value="succeeded">succeeded</option>
                <option value="partially_failed">partially_failed</option>
                <option value="failed">failed</option>
              </select>
            </div>
            <div class="field-group">
              <label for="task-trigger-filter">触发方式</label>
              <select id="task-trigger-filter" name="trigger_type">
                <option value="">全部</option>
                <option value="admin">admin</option>
                <option value="cron">cron</option>
                <option value="manual">manual</option>
              </select>
            </div>
            <div class="field-group">
              <label for="task-source-filter">来源类型</label>
              <select id="task-source-filter" name="source_type">
                <option value="">全部</option>
                <option value="bing">bing</option>
                <option value="nasa_apod">nasa_apod</option>
              </select>
            </div>
            <div class="field-group">
              <label for="task-created-from">创建开始时间</label>
              <input id="task-created-from" name="created_from_utc" type="datetime-local" />
            </div>
            <div class="field-group">
              <label for="task-created-to">创建结束时间</label>
              <input id="task-created-to" name="created_to_utc" type="datetime-local" />
            </div>
            <div class="field-group">
              <label for="task-page-size">每页数量</label>
              <select id="task-page-size" name="page_size">
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
              </select>
            </div>
          </div>
          <div class="button-row">
            <button class="primary-button" type="submit">刷新任务列表</button>
            <button class="ghost-button" id="reset-task-filters" type="button">重置筛选</button>
          </div>
        </form>
      </article>
    </section>
    <section class="table-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>任务</th>
              <th>状态</th>
              <th>参数</th>
              <th>统计</th>
              <th>错误摘要</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody id="task-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="button-row" id="task-pagination" aria-label="后台任务分页"></nav>
  `;

  const createForm = document.querySelector("#task-create-form");
  const createFeedback = document.querySelector("#task-create-feedback");
  const filterForm = document.querySelector("#task-filter-form");
  const tableBody = document.querySelector("#task-table-body");
  const paginationNode = document.querySelector("#task-pagination");
  const sourceSelect = document.querySelector("#task-source-type");
  const marketInput = document.querySelector("#task-market-code");

  if (
    !(createForm instanceof HTMLFormElement) ||
    !(createFeedback instanceof HTMLElement) ||
    !(filterForm instanceof HTMLFormElement) ||
    !(tableBody instanceof HTMLElement) ||
    !(paginationNode instanceof HTMLElement) ||
    !(sourceSelect instanceof HTMLSelectElement) ||
    !(marketInput instanceof HTMLInputElement)
  ) {
    return;
  }

  assignFormValue(filterForm, "task_status", state.task_status);
  assignFormValue(filterForm, "trigger_type", state.trigger_type);
  assignFormValue(filterForm, "source_type", state.source_type);
  assignFormValue(filterForm, "created_from_utc", state.created_from_utc);
  assignFormValue(filterForm, "created_to_utc", state.created_to_utc);
  assignFormValue(filterForm, "page_size", state.page_size);

  if (items.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="notice-card">
            <h3>当前没有匹配任务</h3>
            <p>可以先创建手动采集任务，或调整筛选条件。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    tableBody.innerHTML = items.map((item) => renderTaskRow(item)).join("");
  }

  paginationNode.innerHTML = renderPaginationLinks("/admin/tasks", state, pagination.total_pages);

  const syncMarketCode = () => {
    marketInput.value = sourceSelect.value === "nasa_apod" ? "global" : "en-US";
  };
  syncMarketCode();
  sourceSelect.addEventListener("change", syncMarketCode);

  createForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(createForm);
    setNotice(createFeedback, "正在创建任务...", "系统会先写入 queued 任务，再由 cron 近实时消费。");
    try {
      const response = await fetchAdmin("/api/admin/collection-tasks", {
        method: "POST",
        token: session.session_token,
        body: JSON.stringify({
          source_type: stringValue(formData.get("source_type")) || "bing",
          market_code: stringValue(formData.get("market_code")),
          date_from: stringValue(formData.get("date_from")),
          date_to: stringValue(formData.get("date_to")),
          force_refresh: formData.get("force_refresh") === "on",
        }),
      });
      redirectTo(`/admin/tasks/${encodeURIComponent(String(response.task_id))}`);
    } catch (error) {
      console.error(error);
      const message = error instanceof ApiError ? error.message : "创建任务失败，请稍后重试。";
      setNotice(createFeedback, "创建失败", message);
    }
  });

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const nextState = {
      task_status: stringValue(formData.get("task_status")),
      trigger_type: stringValue(formData.get("trigger_type")),
      source_type: stringValue(formData.get("source_type")),
      created_from_utc: stringValue(formData.get("created_from_utc")),
      created_to_utc: stringValue(formData.get("created_to_utc")),
      page_size: stringValue(formData.get("page_size")) || "20",
      page: "1",
    };
    redirectTo(`/admin/tasks?${buildTaskParams(nextState).toString()}`);
  });

  const resetButton = document.querySelector("#reset-task-filters");
  if (resetButton instanceof HTMLButtonElement) {
    resetButton.addEventListener("click", () => {
      redirectTo("/admin/tasks?page=1&page_size=20");
    });
  }

  bindTaskConsumeActions(session);
  bindTaskRetryActions(session);
}

async function renderTaskDetailPage(session, id) {
  setLoadingState("正在读取任务详情...");

  try {
    const payload = await fetchAdmin(`/api/admin/collection-tasks/${encodeURIComponent(id)}`, {
      token: session.session_token,
    });
    renderTaskDetailView(session, payload.data);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderTaskDetailView(session, detail) {
  const items = Array.isArray(detail.items) ? detail.items : [];
  const snapshot = detail.request_snapshot || {};
  const allowConsume = detail.task_status === "queued";
  const allowRetry = detail.task_status === "failed" || detail.task_status === "partially_failed";

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>任务 #${escapeHtml(String(detail.id))}</h2>
        <p class="muted-copy">任务详情通过 <code>/api/admin/collection-tasks/${escapeHtml(String(detail.id))}</code> 读取。</p>
      </div>
      <div class="button-row">
        <a class="ghost-button" href="/admin/tasks">返回任务列表</a>
        <a class="ghost-button" href="/admin/logs?task_id=${escapeHtml(String(detail.id))}">查看结构化日志</a>
      </div>
    </div>
    <div id="task-detail-feedback"></div>
    <section class="detail-grid">
      <article class="detail-card">
        <h3>当前状态</h3>
        <dl class="detail-list">
          ${renderDetailRow("任务类型", detail.task_type)}
          ${renderDetailRow("来源类型", detail.source_type)}
          ${renderDetailRow("触发方式", detail.trigger_type)}
          ${renderDetailRow("触发人", detail.triggered_by || "无")}
          ${renderDetailRow("任务状态", detail.task_status)}
          ${renderDetailRow("重试源任务", detail.retry_of_task_id ? String(detail.retry_of_task_id) : "无")}
          ${renderDetailRow("开始时间", detail.started_at_utc || "未开始")}
          ${renderDetailRow("结束时间", detail.finished_at_utc || "未结束")}
        </dl>
        <div class="button-row">
          ${allowConsume ? `<button class="primary-button" type="button" data-task-consume="${escapeHtml(String(detail.id))}">立即执行该任务</button>` : ""}
          ${allowRetry ? `<button class="primary-button" type="button" data-task-retry="${escapeHtml(String(detail.id))}">重试该任务</button>` : ""}
        </div>
      </article>
      <article class="detail-card">
        <h3>请求参数快照</h3>
        <dl class="detail-list">
          ${renderDetailRow("地区", snapshot.market_code || "无")}
          ${renderDetailRow("开始日期", snapshot.date_from || "无")}
          ${renderDetailRow("结束日期", snapshot.date_to || "无")}
          ${renderDetailRow("force_refresh", formatBoolean(snapshot.force_refresh))}
        </dl>
      </article>
      <article class="detail-card detail-card-wide">
        <h3>执行统计</h3>
        <div class="stats-grid">
          <div class="stats-card">
            <strong>${escapeHtml(String(detail.success_count))}</strong>
            <span>成功</span>
          </div>
          <div class="stats-card">
            <strong>${escapeHtml(String(detail.duplicate_count))}</strong>
            <span>重复</span>
          </div>
          <div class="stats-card">
            <strong>${escapeHtml(String(detail.failure_count))}</strong>
            <span>失败</span>
          </div>
        </div>
        <div class="notice-card">
          <h4>错误摘要</h4>
          <p>${escapeHtml(detail.error_summary || "当前没有错误摘要。")}</p>
        </div>
      </article>
      <article class="detail-card detail-card-wide">
        <h3>逐条处理明细</h3>
        ${
          items.length === 0
            ? `<div class="notice-card"><h4>暂无处理明细</h4><p>任务尚未执行，或当前没有结构化明细。</p></div>`
            : `
              <div class="table-wrapper">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>来源项</th>
                      <th>动作</th>
                      <th>结果</th>
                      <th>定位信息</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${items.map((item) => renderTaskItemRow(item)).join("")}
                  </tbody>
                </table>
              </div>
            `
        }
      </article>
    </section>
  `;

  const feedback = document.querySelector("#task-detail-feedback");
  if (!(feedback instanceof HTMLElement)) {
    return;
  }

  bindTaskConsumeActions(session, feedback);
  bindTaskRetryActions(session, feedback);
}

async function renderLogPage(session) {
  setLoadingState("正在读取结构化日志...");

  try {
    const state = readLogState();
    const payload = await fetchAdmin(`/api/admin/logs?${buildLogParams(state).toString()}`, {
      token: session.session_token,
    });
    renderLogView(payload, state);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderLogView(payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];
  const pagination = payload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>结构化日志查询</h2>
        <p class="muted-copy">当前读取 <code>collection_task_items</code> 结构化日志，不直接暴露服务器原始日志文件。</p>
      </div>
      <p class="meta-pill">共 ${pagination.total} 条</p>
    </div>
    <form class="admin-form" id="log-filter-form">
      <div class="filter-grid">
        <div class="field-group">
          <label for="log-task-id">任务 ID</label>
          <input id="log-task-id" name="task_id" type="number" min="1" />
        </div>
        <div class="field-group">
          <label for="log-error-type">错误类型 / 结果</label>
          <input id="log-error-type" name="error_type" type="text" placeholder="例如 failed" />
        </div>
        <div class="field-group">
          <label for="log-started-from">开始时间</label>
          <input id="log-started-from" name="started_from_utc" type="datetime-local" />
        </div>
        <div class="field-group">
          <label for="log-started-to">结束时间</label>
          <input id="log-started-to" name="started_to_utc" type="datetime-local" />
        </div>
        <div class="field-group">
          <label for="log-page-size">每页数量</label>
          <select id="log-page-size" name="page_size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </div>
      </div>
      <div class="button-row">
        <button class="primary-button" type="submit">刷新日志</button>
        <button class="ghost-button" id="reset-log-filters" type="button">重置筛选</button>
      </div>
    </form>
    <section class="table-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>任务</th>
              <th>动作</th>
              <th>结果</th>
              <th>失败原因</th>
              <th>定位</th>
            </tr>
          </thead>
          <tbody id="log-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="button-row" id="log-pagination" aria-label="后台日志分页"></nav>
  `;

  const filterForm = document.querySelector("#log-filter-form");
  const tableBody = document.querySelector("#log-table-body");
  const paginationNode = document.querySelector("#log-pagination");

  if (
    !(filterForm instanceof HTMLFormElement) ||
    !(tableBody instanceof HTMLElement) ||
    !(paginationNode instanceof HTMLElement)
  ) {
    return;
  }

  assignFormValue(filterForm, "task_id", state.task_id);
  assignFormValue(filterForm, "error_type", state.error_type);
  assignFormValue(filterForm, "started_from_utc", state.started_from_utc);
  assignFormValue(filterForm, "started_to_utc", state.started_to_utc);
  assignFormValue(filterForm, "page_size", state.page_size);

  if (items.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="notice-card">
            <h3>当前没有匹配日志</h3>
            <p>可以按任务 ID、错误类型或时间范围继续筛选。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    tableBody.innerHTML = items.map((item) => renderLogRow(item)).join("");
  }

  paginationNode.innerHTML = renderPaginationLinks("/admin/logs", state, pagination.total_pages);

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const nextState = {
      task_id: stringValue(formData.get("task_id")),
      error_type: stringValue(formData.get("error_type")),
      started_from_utc: stringValue(formData.get("started_from_utc")),
      started_to_utc: stringValue(formData.get("started_to_utc")),
      page_size: stringValue(formData.get("page_size")) || "20",
      page: "1",
    };
    redirectTo(`/admin/logs?${buildLogParams(nextState).toString()}`);
  });

  const resetButton = document.querySelector("#reset-log-filters");
  if (resetButton instanceof HTMLButtonElement) {
    resetButton.addEventListener("click", () => {
      redirectTo("/admin/logs?page=1&page_size=20");
    });
  }
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

async function renderDownloadStatsPage(session) {
  setLoadingState("正在读取下载统计...");

  try {
    const state = readDownloadStatsState();
    const payload = await fetchAdmin(
      `/api/admin/download-stats?${buildDownloadStatsParams(state).toString()}`,
      { token: session.session_token },
    );
    renderDownloadStatsView(payload, state);
  } catch (error) {
    handleAdminError(error);
  }
}

function renderDownloadStatsView(payload, state) {
  const summary = payload.summary || payload.data?.summary || {};
  const topWallpapers = Array.isArray(payload.top_wallpapers || payload.data?.top_wallpapers)
    ? payload.top_wallpapers || payload.data.top_wallpapers
    : [];
  const dailyTrends = Array.isArray(payload.daily_trends || payload.data?.daily_trends)
    ? payload.daily_trends || payload.data.daily_trends
    : [];

  adminRoot.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>后台下载统计</h2>
        <p class="muted-copy">只统计下载登记事件，真实文件仍由静态资源链路提供，不经过应用服务传大文件。</p>
      </div>
      <p class="meta-pill">最近 ${escapeHtml(state.days || "7")} 天</p>
    </div>
    <form class="admin-form" id="download-stats-form">
      <div class="filter-grid">
        <div class="field-group">
          <label for="download-days">统计窗口</label>
          <select id="download-days" name="days">
            <option value="7">最近 7 天</option>
            <option value="30">最近 30 天</option>
            <option value="90">最近 90 天</option>
          </select>
        </div>
        <div class="field-group">
          <label for="download-top-limit">热门内容数量</label>
          <select id="download-top-limit" name="top_limit">
            <option value="5">5</option>
            <option value="10">10</option>
            <option value="20">20</option>
          </select>
        </div>
      </div>
      <div class="button-row">
        <button class="primary-button" type="submit">刷新统计</button>
        <button class="ghost-button" id="reset-download-stats" type="button">恢复默认</button>
      </div>
    </form>
    <section class="stats-grid">
      <article class="stats-card">
        <span class="muted-inline">下载事件总数</span>
        <strong>${escapeHtml(summary.total_events || 0)}</strong>
      </article>
      <article class="stats-card">
        <span class="muted-inline">成功跳转</span>
        <strong>${escapeHtml(summary.redirected_events || 0)}</strong>
      </article>
      <article class="stats-card">
        <span class="muted-inline">已拦截</span>
        <strong>${escapeHtml(summary.blocked_events || 0)}</strong>
      </article>
      <article class="stats-card">
        <span class="muted-inline">登记降级</span>
        <strong>${escapeHtml(summary.degraded_events || 0)}</strong>
      </article>
      <article class="stats-card">
        <span class="muted-inline">涉及内容数</span>
        <strong>${escapeHtml(summary.unique_wallpapers || 0)}</strong>
      </article>
      <article class="stats-card">
        <span class="muted-inline">最近一次事件</span>
        <strong>${escapeHtml(summary.latest_occurred_at_utc || "暂无记录")}</strong>
      </article>
    </section>
    <div class="detail-grid">
      <section class="table-card detail-card-wide">
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>热门内容</th>
                <th>地区</th>
                <th>日期</th>
                <th>成功下载数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody id="download-top-table-body"></tbody>
          </table>
        </div>
      </section>
      <section class="table-card detail-card-wide">
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>总事件</th>
                <th>成功跳转</th>
                <th>已拦截</th>
                <th>登记降级</th>
              </tr>
            </thead>
            <tbody id="download-trend-table-body"></tbody>
          </table>
        </div>
      </section>
    </div>
  `;

  const form = document.querySelector("#download-stats-form");
  const topTableBody = document.querySelector("#download-top-table-body");
  const trendTableBody = document.querySelector("#download-trend-table-body");
  if (
    !(form instanceof HTMLFormElement) ||
    !(topTableBody instanceof HTMLElement) ||
    !(trendTableBody instanceof HTMLElement)
  ) {
    return;
  }

  assignFormValue(form, "days", state.days);
  assignFormValue(form, "top_limit", state.top_limit);

  if (topWallpapers.length === 0) {
    topTableBody.innerHTML = `
      <tr>
        <td colspan="5">
          <div class="notice-card">
            <h3>当前时间窗口内没有成功下载记录</h3>
            <p>可以先通过公开详情页触发下载登记，再回来查看热门内容。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    topTableBody.innerHTML = topWallpapers
      .map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.title)}</td>
            <td>${escapeHtml(item.market_code)}</td>
            <td>${escapeHtml(item.wallpaper_date)}</td>
            <td>${escapeHtml(item.download_count)}</td>
            <td><a class="mini-button" href="/admin/wallpapers/${encodeURIComponent(String(item.wallpaper_id))}">查看详情</a></td>
          </tr>
        `,
      )
      .join("");
  }

  if (dailyTrends.length === 0) {
    trendTableBody.innerHTML = `
      <tr>
        <td colspan="5">
          <div class="notice-card">
            <h3>当前没有趋势数据</h3>
            <p>下载登记事件产生后，这里会按天展示成功、拦截和降级趋势。</p>
          </div>
        </td>
      </tr>
    `;
  } else {
    trendTableBody.innerHTML = dailyTrends
      .map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.trend_date)}</td>
            <td>${escapeHtml(item.total_events)}</td>
            <td>${escapeHtml(item.redirected_events)}</td>
            <td>${escapeHtml(item.blocked_events)}</td>
            <td>${escapeHtml(item.degraded_events)}</td>
          </tr>
        `,
      )
      .join("");
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    redirectTo(
      `/admin/download-stats?${buildDownloadStatsParams({
        days: stringValue(formData.get("days")) || "7",
        top_limit: stringValue(formData.get("top_limit")) || "5",
      }).toString()}`,
    );
  });

  const resetButton = document.querySelector("#reset-download-stats");
  if (resetButton instanceof HTMLButtonElement) {
    resetButton.addEventListener("click", () => {
      redirectTo("/admin/download-stats?days=7&top_limit=5");
    });
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
            <option value="tag">tag</option>
            <option value="collection_task">collection_task</option>
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
    const selectedIds = formData.getAll("tag_ids").map((value) => Number(value)).filter((value) => Number.isInteger(value) && value > 0);
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

function bindTaskRetryActions(session, feedbackNode = null) {
  document.querySelectorAll("[data-task-retry]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", async () => {
      const targetId = button.dataset.taskRetry;
      if (!targetId) {
        return;
      }
      const confirmed = window.confirm(`确认重试任务 ${targetId} 吗？`);
      if (!confirmed) {
        return;
      }
      if (feedbackNode instanceof HTMLElement) {
        setNotice(feedbackNode, "正在创建重试任务...", "系统会复制原任务参数并创建新的 queued 任务。");
      }
      try {
        const response = await fetchAdmin(`/api/admin/collection-tasks/${encodeURIComponent(targetId)}/retry`, {
          method: "POST",
          token: session.session_token,
        });
        redirectTo(`/admin/tasks/${encodeURIComponent(String(response.task_id))}`);
      } catch (error) {
        console.error(error);
        const message = error instanceof ApiError ? error.message : "任务重试失败，请稍后重试。";
        if (feedbackNode instanceof HTMLElement) {
          setNotice(feedbackNode, "重试失败", message);
        } else {
          window.alert(message);
        }
      }
    });
  });
}

function bindTaskConsumeActions(session, feedbackNode = null) {
  document.querySelectorAll("[data-task-consume]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", async () => {
      const targetId = button.dataset.taskConsume;
      if (!targetId) {
        return;
      }
      const confirmed = window.confirm(`确认立即执行任务 ${targetId} 吗？`);
      if (!confirmed) {
        return;
      }
      if (feedbackNode instanceof HTMLElement) {
        setNotice(feedbackNode, "正在手动触发任务...", "系统会立即执行该 queued 任务，并保留原有 cron 消费机制。");
      }
      try {
        await fetchAdmin(`/api/admin/collection-tasks/${encodeURIComponent(targetId)}/consume`, {
          method: "POST",
          token: session.session_token,
        });
        redirectTo(`/admin/tasks/${encodeURIComponent(String(targetId))}`);
      } catch (error) {
        console.error(error);
        const message = error instanceof ApiError ? error.message : "任务手动触发失败，请稍后重试。";
        if (feedbackNode instanceof HTMLElement) {
          setNotice(feedbackNode, "触发失败", message);
        } else {
          window.alert(message);
        }
      }
    });
  });
}

function bindTagEditActions(items) {
  document.querySelectorAll("[data-tag-edit]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", () => {
      const targetId = Number(button.dataset.tagEdit);
      const tag = items.find((item) => Number(item.id) === targetId);
      const form = document.querySelector("#tag-form");
      const feedback = document.querySelector("#tag-form-feedback");
      if (!tag || !(form instanceof HTMLFormElement)) {
        return;
      }
      assignFormValue(form, "tag_id", String(tag.id));
      assignFormValue(form, "tag_key", tag.tag_key);
      assignFormValue(form, "tag_name", tag.tag_name);
      assignFormValue(form, "tag_category", tag.tag_category || "");
      assignFormValue(form, "status", tag.status);
      assignFormValue(form, "sort_weight", String(tag.sort_weight));
      assignFormValue(form, "operator_reason", `更新标签 ${tag.tag_key}`);
      if (feedback instanceof HTMLElement) {
        setNotice(feedback, "已载入标签", `正在编辑标签 ${tag.tag_name} (${tag.tag_key})。修改后提交即可更新。`);
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
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

function renderStatusButton(wallpaperIdValue, targetStatus, label) {
  return `<button class="mini-button" type="button" data-wallpaper-id="${escapeHtml(String(wallpaperIdValue))}" data-status-action="${escapeHtml(targetStatus)}">${escapeHtml(label)}</button>`;
}

function renderTaskRow(item) {
  return `
    <tr>
      <td>
        <div class="table-title">
          <strong>#${escapeHtml(String(item.id))}</strong>
          <span>${escapeHtml(item.task_type)} / ${escapeHtml(item.trigger_type)}</span>
        </div>
      </td>
      <td>
        <div class="stacked-copy">
          <span class="status-badge">${escapeHtml(item.task_status)}</span>
          <span class="muted-inline">${escapeHtml(item.started_at_utc || "未开始")}</span>
        </div>
      </td>
      <td>
        <div class="stacked-copy">
          <span>${escapeHtml(item.source_type)} / ${escapeHtml(item.market_code || "无地区")}</span>
          <span class="muted-inline">${escapeHtml(item.date_from || "无")} ~ ${escapeHtml(item.date_to || "无")}</span>
        </div>
      </td>
      <td>
        <div class="stacked-copy">
          <span>成功 ${escapeHtml(String(item.success_count))}</span>
          <span class="muted-inline">重复 ${escapeHtml(String(item.duplicate_count))} / 失败 ${escapeHtml(String(item.failure_count))}</span>
        </div>
      </td>
      <td>${escapeHtml(item.error_summary || "无")}</td>
      <td>
        <div class="button-row">
          <a class="inline-link" href="/admin/tasks/${escapeHtml(String(item.id))}">详情</a>
          <a class="inline-link" href="/admin/logs?task_id=${escapeHtml(String(item.id))}">日志</a>
          ${renderConsumeButton(item)}
          ${renderRetryButton(item)}
        </div>
      </td>
    </tr>
  `;
}

function renderTagRow(item) {
  return `
    <tr>
      <td>
        <div class="table-title">
          <strong>${escapeHtml(item.tag_name)}</strong>
          <span><code>${escapeHtml(item.tag_key)}</code></span>
        </div>
      </td>
      <td><span class="status-badge">${escapeHtml(item.status)}</span></td>
      <td>${escapeHtml(item.tag_category || "未分类")}</td>
      <td>${escapeHtml(String(item.sort_weight))}</td>
      <td>${escapeHtml(String(item.wallpaper_count))}</td>
      <td>
        <div class="button-row">
          <button class="mini-button" type="button" data-tag-edit="${escapeHtml(String(item.id))}">编辑</button>
          <a class="inline-link" href="/admin/audit-logs?target_type=tag&target_id=${escapeHtml(String(item.id))}">审计</a>
        </div>
      </td>
    </tr>
  `;
}

function renderRetryButton(item) {
  if (item.task_status !== "failed" && item.task_status !== "partially_failed") {
    return "";
  }
  return `<button class="mini-button" type="button" data-task-retry="${escapeHtml(String(item.id))}">重试</button>`;
}

function renderConsumeButton(item) {
  if (item.task_status !== "queued") {
    return "";
  }
  return `<button class="mini-button" type="button" data-task-consume="${escapeHtml(String(item.id))}">立即执行</button>`;
}

function renderTaskItemRow(item) {
  return `
    <tr>
      <td>${escapeHtml(item.occurred_at_utc)}</td>
      <td><code>${escapeHtml(item.source_item_key || "-")}</code></td>
      <td>${escapeHtml(item.action_name)}</td>
      <td>${escapeHtml(item.result_status)}</td>
      <td><pre>${escapeHtml(JSON.stringify({
        dedupe_hit_type: item.dedupe_hit_type,
        db_write_result: item.db_write_result,
        file_write_result: item.file_write_result,
        failure_reason: item.failure_reason,
      }, null, 2))}</pre></td>
    </tr>
  `;
}

function renderLogRow(item) {
  return `
    <tr>
      <td>${escapeHtml(item.occurred_at_utc)}</td>
      <td>
        <div class="stacked-copy">
          <span><a class="inline-link" href="/admin/tasks/${escapeHtml(String(item.task_id))}">#${escapeHtml(String(item.task_id))}</a></span>
          <span class="muted-inline">${escapeHtml(item.task_status)} / ${escapeHtml(item.trigger_type)}</span>
        </div>
      </td>
      <td>${escapeHtml(item.action_name)}</td>
      <td>${escapeHtml(item.result_status)}</td>
      <td>${escapeHtml(item.failure_reason || "无")}</td>
      <td><pre>${escapeHtml(JSON.stringify({
        source_item_key: item.source_item_key,
        dedupe_hit_type: item.dedupe_hit_type,
        db_write_result: item.db_write_result,
        file_write_result: item.file_write_result,
      }, null, 2))}</pre></td>
    </tr>
  `;
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
  let params = buildWallpaperListParams(nextState);
  if (basePath.includes("/admin/audit-logs")) {
    params = buildAuditParams(nextState);
  } else if (basePath === "/admin/tags") {
    params = buildTagParams(nextState);
  } else if (basePath === "/admin/tasks") {
    params = buildTaskParams(nextState);
  } else if (basePath === "/admin/logs") {
    params = buildLogParams(nextState);
  }
  return `${basePath}?${params.toString()}`;
}

function readWallpaperListState() {
  const params = new URLSearchParams(window.location.search);
  return {
    keyword: params.get("keyword") || "",
    content_status: params.get("content_status") || "",
    image_status: params.get("image_status") || "",
    market_code: params.get("market_code") || "",
    created_from_utc: toDatetimeLocalValue(params.get("created_from_utc")),
    created_to_utc: toDatetimeLocalValue(params.get("created_to_utc")),
    page: params.get("page") || "1",
    page_size: params.get("page_size") || "20",
  };
}

function readTaskListState() {
  const params = new URLSearchParams(window.location.search);
  return {
    task_status: params.get("task_status") || "",
    trigger_type: params.get("trigger_type") || "",
    source_type: params.get("source_type") || "",
    created_from_utc: toDatetimeLocalValue(params.get("created_from_utc")),
    created_to_utc: toDatetimeLocalValue(params.get("created_to_utc")),
    page: params.get("page") || "1",
    page_size: params.get("page_size") || "20",
  };
}

function readTagState() {
  const params = new URLSearchParams(window.location.search);
  return {
    status: params.get("status") || "",
    tag_category: params.get("tag_category") || "",
  };
}

function readDownloadStatsState() {
  const params = new URLSearchParams(window.location.search);
  return {
    days: params.get("days") || "7",
    top_limit: params.get("top_limit") || "5",
  };
}

function readLogState() {
  const params = new URLSearchParams(window.location.search);
  return {
    task_id: params.get("task_id") || "",
    error_type: params.get("error_type") || "",
    started_from_utc: toDatetimeLocalValue(params.get("started_from_utc")),
    started_to_utc: toDatetimeLocalValue(params.get("started_to_utc")),
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
  setOptionalParam(params, "keyword", state.keyword);
  setOptionalParam(params, "content_status", state.content_status);
  setOptionalParam(params, "image_status", state.image_status);
  setOptionalParam(params, "market_code", state.market_code);
  setOptionalParam(params, "created_from_utc", toUtcQueryValue(state.created_from_utc));
  setOptionalParam(params, "created_to_utc", toUtcQueryValue(state.created_to_utc));
  return params;
}

function buildTaskParams(state) {
  const params = new URLSearchParams();
  params.set("page", state.page || "1");
  params.set("page_size", state.page_size || "20");
  setOptionalParam(params, "task_status", state.task_status);
  setOptionalParam(params, "trigger_type", state.trigger_type);
  setOptionalParam(params, "source_type", state.source_type);
  setOptionalParam(params, "created_from_utc", toUtcQueryValue(state.created_from_utc));
  setOptionalParam(params, "created_to_utc", toUtcQueryValue(state.created_to_utc));
  return params;
}

function buildTagParams(state) {
  const params = new URLSearchParams();
  setOptionalParam(params, "status", state.status);
  setOptionalParam(params, "tag_category", state.tag_category);
  return params;
}

function buildDownloadStatsParams(state) {
  const params = new URLSearchParams();
  params.set("days", state.days || "7");
  params.set("top_limit", state.top_limit || "5");
  return params;
}

function buildLogParams(state) {
  const params = new URLSearchParams();
  params.set("page", state.page || "1");
  params.set("page_size", state.page_size || "20");
  setOptionalParam(params, "task_id", state.task_id);
  setOptionalParam(params, "error_type", state.error_type);
  setOptionalParam(params, "started_from_utc", toUtcQueryValue(state.started_from_utc));
  setOptionalParam(params, "started_to_utc", toUtcQueryValue(state.started_to_utc));
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
        <a class="ghost-button" href="/admin/tasks">返回采集任务</a>
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

function formatBoolean(value) {
  return value ? "true" : "false";
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
