import {
  adminRoot,
  assignFormValue,
  buildAuditParams,
  buildDownloadStatsParams,
  buildLogParams,
  escapeHtml,
  fetchAdmin,
  handleAdminError,
  readAuditState,
  readDownloadStatsState,
  readLogState,
  redirectTo,
  renderPaginationLinks,
  setLoadingState,
  TW,
} from "../modules/core.js";

export async function renderLogPage(session) {
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

export async function renderDownloadStatsPage(session) {
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

export async function renderAuditPage(session) {
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

function renderLogView(payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];
  const pagination = payload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };

  adminRoot.innerHTML = `
    <div class="${TW.panelHead}">
      <div>
        <h2>结构化日志查询</h2>
        <p class="${TW.mutedCopy}">当前读取 <code>collection_task_items</code> 结构化日志，不直接暴露服务器原始日志文件。</p>
      </div>
      <p class="${TW.metaPill}">共 ${pagination.total} 条</p>
    </div>
    <form class="${TW.form}" id="log-filter-form">
      <div class="${TW.filterGrid}">
        <div class="${TW.field}">
          <label class="${TW.label}" for="log-task-id">任务 ID</label>
          <input class="${TW.input}" id="log-task-id" name="task_id" type="number" min="1" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="log-error-type">错误类型 / 结果</label>
          <input class="${TW.input}" id="log-error-type" name="error_type" type="text" placeholder="例如 failed" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="log-started-from">开始时间</label>
          <input class="${TW.input}" id="log-started-from" name="started_from_utc" type="datetime-local" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="log-started-to">结束时间</label>
          <input class="${TW.input}" id="log-started-to" name="started_to_utc" type="datetime-local" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="log-page-size">每页数量</label>
          <select class="${TW.input}" id="log-page-size" name="page_size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </div>
      </div>
      <div class="${TW.btnRow}">
        <button class="${TW.primaryBtn}" type="submit">刷新日志</button>
        <button class="${TW.ghostBtn}" id="reset-log-filters" type="button">重置筛选</button>
      </div>
    </form>
    <section class="${TW.tableCard}">
      <div class="${TW.tableWrapper}">
        <table class="${TW.dataTable}">
          <thead>
            <tr>
              <th class="${TW.th}">时间</th>
              <th class="${TW.th}">任务</th>
              <th class="${TW.th}">动作</th>
              <th class="${TW.th}">结果</th>
              <th class="${TW.th}">失败原因</th>
              <th class="${TW.th}">定位</th>
            </tr>
          </thead>
          <tbody id="log-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="${TW.btnRow}" id="log-pagination" aria-label="后台日志分页"></nav>
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
        <td colspan="6" class="${TW.td}">
          <div class="${TW.notice}">
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
      task_id: formData.get("task_id"),
      error_type: formData.get("error_type"),
      started_from_utc: formData.get("started_from_utc"),
      started_to_utc: formData.get("started_to_utc"),
      page_size: formData.get("page_size") || "20",
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

function renderDownloadStatsView(payload, state) {
  const summary = payload.summary || payload.data?.summary || {};
  const topWallpapers = Array.isArray(payload.top_wallpapers || payload.data?.top_wallpapers)
    ? payload.top_wallpapers || payload.data.top_wallpapers
    : [];
  const dailyTrends = Array.isArray(payload.daily_trends || payload.data?.daily_trends)
    ? payload.daily_trends || payload.data.daily_trends
    : [];

  adminRoot.innerHTML = `
    <div class="${TW.panelHead}">
      <div>
        <h2>后台下载统计</h2>
        <p class="${TW.mutedCopy}">只统计下载登记事件，真实文件仍由静态资源链路提供，不经过应用服务传大文件。</p>
      </div>
      <p class="${TW.metaPill}">最近 ${escapeHtml(state.days || "7")} 天</p>
    </div>
    <form class="${TW.form}" id="download-stats-form">
      <div class="${TW.filterGrid}">
        <div class="${TW.field}">
          <label class="${TW.label}" for="download-days">统计窗口</label>
          <select class="${TW.input}" id="download-days" name="days">
            <option value="7">最近 7 天</option>
            <option value="30">最近 30 天</option>
            <option value="90">最近 90 天</option>
          </select>
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="download-top-limit">热门内容数量</label>
          <select class="${TW.input}" id="download-top-limit" name="top_limit">
            <option value="5">5</option>
            <option value="10">10</option>
            <option value="20">20</option>
          </select>
        </div>
      </div>
      <div class="${TW.btnRow}">
        <button class="${TW.primaryBtn}" type="submit">刷新统计</button>
        <button class="${TW.ghostBtn}" id="reset-download-stats" type="button">恢复默认</button>
      </div>
    </form>
    <section class="${TW.statsGrid}">
      <article class="${TW.statsCard}">
        <span class="${TW.mutedInline}">下载事件总数</span>
        <strong>${escapeHtml(summary.total_events || 0)}</strong>
      </article>
      <article class="${TW.statsCard}">
        <span class="${TW.mutedInline}">成功跳转</span>
        <strong>${escapeHtml(summary.redirected_events || 0)}</strong>
      </article>
      <article class="${TW.statsCard}">
        <span class="${TW.mutedInline}">已拦截</span>
        <strong>${escapeHtml(summary.blocked_events || 0)}</strong>
      </article>
      <article class="${TW.statsCard}">
        <span class="${TW.mutedInline}">登记降级</span>
        <strong>${escapeHtml(summary.degraded_events || 0)}</strong>
      </article>
      <article class="${TW.statsCard}">
        <span class="${TW.mutedInline}">涉及内容数</span>
        <strong>${escapeHtml(summary.unique_wallpapers || 0)}</strong>
      </article>
      <article class="${TW.statsCard}">
        <span class="${TW.mutedInline}">最近一次事件</span>
        <strong>${escapeHtml(summary.latest_occurred_at_utc || "暂无记录")}</strong>
      </article>
    </section>
    <div class="${TW.detailGrid}">
      <section class="${TW.tableCard} ${TW.cardWide}">
        <div class="${TW.tableWrapper}">
          <table class="${TW.dataTable}">
            <thead>
              <tr>
                <th class="${TW.th}">热门内容</th>
                <th class="${TW.th}">地区</th>
                <th class="${TW.th}">日期</th>
                <th class="${TW.th}">成功下载数</th>
                <th class="${TW.th}">操作</th>
              </tr>
            </thead>
            <tbody id="download-top-table-body"></tbody>
          </table>
        </div>
      </section>
      <section class="${TW.tableCard} ${TW.cardWide}">
        <div class="${TW.tableWrapper}">
          <table class="${TW.dataTable}">
            <thead>
              <tr>
                <th class="${TW.th}">日期</th>
                <th class="${TW.th}">总事件</th>
                <th class="${TW.th}">成功跳转</th>
                <th class="${TW.th}">已拦截</th>
                <th class="${TW.th}">登记降级</th>
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
        <td colspan="5" class="${TW.td}">
          <div class="${TW.notice}">
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
            <td class="${TW.td}">${escapeHtml(item.title)}</td>
            <td class="${TW.td}">${escapeHtml(item.market_code)}</td>
            <td class="${TW.td}">${escapeHtml(item.wallpaper_date)}</td>
            <td class="${TW.td}">${escapeHtml(item.download_count)}</td>
            <td class="${TW.td}"><a class="${TW.miniBtn}" href="/admin/wallpapers/${encodeURIComponent(String(item.wallpaper_id))}">查看详情</a></td>
          </tr>
        `,
      )
      .join("");
  }

  if (dailyTrends.length === 0) {
    trendTableBody.innerHTML = `
      <tr>
        <td colspan="5" class="${TW.td}">
          <div class="${TW.notice}">
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
            <td class="${TW.td}">${escapeHtml(item.trend_date)}</td>
            <td class="${TW.td}">${escapeHtml(item.total_events)}</td>
            <td class="${TW.td}">${escapeHtml(item.redirected_events)}</td>
            <td class="${TW.td}">${escapeHtml(item.blocked_events)}</td>
            <td class="${TW.td}">${escapeHtml(item.degraded_events)}</td>
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
        days: formData.get("days") || "7",
        top_limit: formData.get("top_limit") || "5",
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
    <div class="${TW.panelHead}">
      <div>
        <h2>后台审计记录</h2>
        <p class="${TW.mutedCopy}">支持按操作者、目标对象和时间范围查询。</p>
      </div>
      <p class="${TW.metaPill}">共 ${pagination.total} 条</p>
    </div>
    <form class="${TW.form}" id="audit-filter-form">
      <div class="${TW.filterGrid}">
        <div class="${TW.field}">
          <label class="${TW.label}" for="admin-user-id">管理员 ID</label>
          <input class="${TW.input}" id="admin-user-id" name="admin_user_id" type="number" min="1" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="target-type">目标类型</label>
          <select class="${TW.input}" id="target-type" name="target_type">
            <option value="">全部</option>
            <option value="wallpaper">wallpaper</option>
            <option value="tag">tag</option>
            <option value="collection_task">collection_task</option>
            <option value="admin_session">admin_session</option>
          </select>
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="target-id">目标 ID</label>
          <input class="${TW.input}" id="target-id" name="target_id" type="text" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="started-from">开始时间</label>
          <input class="${TW.input}" id="started-from" name="started_from_utc" type="datetime-local" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="started-to">结束时间</label>
          <input class="${TW.input}" id="started-to" name="started_to_utc" type="datetime-local" />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="audit-page-size">每页数量</label>
          <select class="${TW.input}" id="audit-page-size" name="page_size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </div>
      </div>
      <div class="${TW.btnRow}">
        <button class="${TW.primaryBtn}" type="submit">刷新审计记录</button>
        <button class="${TW.ghostBtn}" id="reset-audit-filters" type="button">重置筛选</button>
      </div>
    </form>
    <section class="${TW.tableCard}">
      <div class="${TW.tableWrapper}">
        <table class="${TW.dataTable}">
          <thead>
            <tr>
              <th class="${TW.th}">时间</th>
              <th class="${TW.th}">操作者</th>
              <th class="${TW.th}">动作</th>
              <th class="${TW.th}">目标</th>
              <th class="${TW.th}">trace_id</th>
              <th class="${TW.th}">状态快照</th>
            </tr>
          </thead>
          <tbody id="audit-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="${TW.btnRow}" id="audit-pagination" aria-label="后台审计分页"></nav>
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
        <td colspan="6" class="${TW.td}">
          <div class="${TW.notice}">
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
      admin_user_id: formData.get("admin_user_id"),
      target_type: formData.get("target_type"),
      target_id: formData.get("target_id"),
      started_from_utc: formData.get("started_from_utc"),
      started_to_utc: formData.get("started_to_utc"),
      page_size: formData.get("page_size") || "20",
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

function renderLogRow(item) {
  return `
    <tr>
      <td class="${TW.td}">${escapeHtml(item.occurred_at_utc)}</td>
      <td class="${TW.td}">
        <div class="${TW.stackedCopy}">
          <span><a class="${TW.inlineLink}" href="/admin/tasks/${escapeHtml(String(item.task_id))}">#${escapeHtml(String(item.task_id))}</a></span>
          <span class="${TW.mutedInline}">${escapeHtml(item.task_status)} / ${escapeHtml(item.trigger_type)}</span>
        </div>
      </td>
      <td class="${TW.td}">${escapeHtml(item.action_name)}</td>
      <td class="${TW.td}">${escapeHtml(item.result_status)}</td>
      <td class="${TW.td}">${escapeHtml(item.failure_reason || "无")}</td>
      <td class="${TW.td}"><pre>${escapeHtml(JSON.stringify({
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
      <td class="${TW.td}">${escapeHtml(item.created_at_utc)}</td>
      <td class="${TW.td}">${escapeHtml(item.admin_username)} (#${escapeHtml(String(item.admin_user_id))})</td>
      <td class="${TW.td}">${escapeHtml(item.action_type)}</td>
      <td class="${TW.td}">${escapeHtml(item.target_type)} / ${escapeHtml(item.target_id)}</td>
      <td class="${TW.td}"><code>${escapeHtml(item.trace_id)}</code></td>
      <td class="${TW.td}"><pre>${escapeHtml(JSON.stringify({ before: item.before_state, after: item.after_state }, null, 2))}</pre></td>
    </tr>
  `;
}
