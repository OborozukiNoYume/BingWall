import {
  adminRoot,
  ApiError,
  assignFormValue,
  buildTaskParams,
  escapeHtml,
  fetchAdmin,
  formatBoolean,
  handleAdminError,
  readTaskListState,
  redirectTo,
  renderDetailRow,
  renderPaginationLinks,
  setLoadingState,
  setNotice,
  statusBadgeClasses,
  stringValue,
  TW,
} from "../modules/core.js";

export async function renderTaskListPage(session) {
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

export async function renderTaskDetailPage(session, id) {
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

function renderTaskListView(session, payload, state) {
  const items = Array.isArray(payload.data.items) ? payload.data.items : [];
  const pagination = payload.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 };

  adminRoot.innerHTML = `
    <div class="${TW.panelHead}">
      <div>
        <h2>采集任务与后台观测</h2>
        <p class="${TW.mutedCopy}">手动创建任务后，可由 cron 自动消费，也可在本页对 queued 任务执行一次人工触发。</p>
      </div>
      <p class="${TW.metaPill}">共 ${pagination.total} 条任务</p>
    </div>
    <section class="${TW.detailGrid}">
      <article class="${TW.card}">
        <h3>创建手动采集任务</h3>
        <form class="${TW.form}" id="task-create-form">
          <div class="${TW.filterGrid}">
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-source-type">来源类型</label>
              <select class="${TW.input}" id="task-source-type" name="source_type">
                <option value="bing">bing</option>
                <option value="nasa_apod">nasa_apod</option>
              </select>
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-market-code">地区</label>
              <input class="${TW.input}" id="task-market-code" name="market_code" type="text" value="en-US" required />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-date-from">开始日期</label>
              <input class="${TW.input}" id="task-date-from" name="date_from" type="date" required />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-date-to">结束日期</label>
              <input class="${TW.input}" id="task-date-to" name="date_to" type="date" required />
            </div>
          </div>
          <label class="${TW.checkboxRow}">
            <input id="task-force-refresh" name="force_refresh" type="checkbox" />
            <span>记录 force_refresh 请求参数</span>
          </label>
          <div class="${TW.btnRow}">
            <button class="${TW.primaryBtn}" type="submit">创建 queued 任务</button>
          </div>
        </form>
        <div id="task-create-feedback"></div>
      </article>
      <article class="${TW.card}">
        <h3>任务筛选</h3>
        <form class="${TW.form}" id="task-filter-form">
          <div class="${TW.filterGrid}">
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-status-filter">任务状态</label>
              <select class="${TW.input}" id="task-status-filter" name="task_status">
                <option value="">全部</option>
                <option value="queued">queued</option>
                <option value="running">running</option>
                <option value="succeeded">succeeded</option>
                <option value="partially_failed">partially_failed</option>
                <option value="failed">failed</option>
              </select>
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-trigger-filter">触发方式</label>
              <select class="${TW.input}" id="task-trigger-filter" name="trigger_type">
                <option value="">全部</option>
                <option value="admin">admin</option>
                <option value="cron">cron</option>
                <option value="manual">manual</option>
              </select>
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-source-filter">来源类型</label>
              <select class="${TW.input}" id="task-source-filter" name="source_type">
                <option value="">全部</option>
                <option value="bing">bing</option>
                <option value="nasa_apod">nasa_apod</option>
              </select>
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-created-from">创建开始时间</label>
              <input class="${TW.input}" id="task-created-from" name="created_from_utc" type="datetime-local" />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-created-to">创建结束时间</label>
              <input class="${TW.input}" id="task-created-to" name="created_to_utc" type="datetime-local" />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="task-page-size">每页数量</label>
              <select class="${TW.input}" id="task-page-size" name="page_size">
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
              </select>
            </div>
          </div>
          <div class="${TW.btnRow}">
            <button class="${TW.primaryBtn}" type="submit">刷新任务列表</button>
            <button class="${TW.ghostBtn}" id="reset-task-filters" type="button">重置筛选</button>
          </div>
        </form>
      </article>
    </section>
    <section class="${TW.tableCard}">
      <div class="${TW.tableWrapper}">
        <table class="${TW.dataTable}">
          <thead>
            <tr>
              <th class="${TW.th}">任务</th>
              <th class="${TW.th}">状态</th>
              <th class="${TW.th}">参数</th>
              <th class="${TW.th}">统计</th>
              <th class="${TW.th}">错误摘要</th>
              <th class="${TW.th}">操作</th>
            </tr>
          </thead>
          <tbody id="task-table-body"></tbody>
        </table>
      </div>
    </section>
    <nav class="${TW.btnRow}" id="task-pagination" aria-label="后台任务分页"></nav>
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
        <td colspan="6" class="${TW.td}">
          <div class="${TW.notice}">
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

function renderTaskDetailView(session, detail) {
  const items = Array.isArray(detail.items) ? detail.items : [];
  const snapshot = detail.request_snapshot || {};
  const allowConsume = detail.task_status === "queued";
  const allowRetry = detail.task_status === "failed" || detail.task_status === "partially_failed";

  adminRoot.innerHTML = `
    <div class="${TW.panelHead}">
      <div>
        <h2>任务 #${escapeHtml(String(detail.id))}</h2>
        <p class="${TW.mutedCopy}">任务详情通过 <code>/api/admin/collection-tasks/${escapeHtml(String(detail.id))}</code> 读取。</p>
      </div>
      <div class="${TW.btnRow}">
        <a class="${TW.ghostBtn}" href="/admin/tasks">返回任务列表</a>
        <a class="${TW.ghostBtn}" href="/admin/logs?task_id=${escapeHtml(String(detail.id))}">查看结构化日志</a>
      </div>
    </div>
    <div id="task-detail-feedback"></div>
    <section class="${TW.detailGrid}">
      <article class="${TW.card}">
        <h3>当前状态</h3>
        <dl class="grid gap-0">
          ${renderDetailRow("任务类型", detail.task_type)}
          ${renderDetailRow("来源类型", detail.source_type)}
          ${renderDetailRow("触发方式", detail.trigger_type)}
          ${renderDetailRow("触发人", detail.triggered_by || "无")}
          ${renderDetailRow("任务状态", detail.task_status)}
          ${renderDetailRow("重试源任务", detail.retry_of_task_id ? String(detail.retry_of_task_id) : "无")}
          ${renderDetailRow("开始时间", detail.started_at_utc || "未开始")}
          ${renderDetailRow("结束时间", detail.finished_at_utc || "未结束")}
        </dl>
        <div class="${TW.btnRow}">
          ${allowConsume ? `<button class="${TW.primaryBtn}" type="button" data-task-consume="${escapeHtml(String(detail.id))}">立即执行该任务</button>` : ""}
          ${allowRetry ? `<button class="${TW.primaryBtn}" type="button" data-task-retry="${escapeHtml(String(detail.id))}">重试该任务</button>` : ""}
        </div>
      </article>
      <article class="${TW.card}">
        <h3>请求参数快照</h3>
        <dl class="grid gap-0">
          ${renderDetailRow("地区", snapshot.market_code || "无")}
          ${renderDetailRow("开始日期", snapshot.date_from || "无")}
          ${renderDetailRow("结束日期", snapshot.date_to || "无")}
          ${renderDetailRow("force_refresh", formatBoolean(snapshot.force_refresh))}
        </dl>
      </article>
      <article class="${TW.card} ${TW.cardWide}">
        <h3>执行统计</h3>
        <div class="${TW.statsGrid}">
          <div class="${TW.statsCard}">
            <strong>${escapeHtml(String(detail.success_count))}</strong>
            <span>成功</span>
          </div>
          <div class="${TW.statsCard}">
            <strong>${escapeHtml(String(detail.duplicate_count))}</strong>
            <span>重复</span>
          </div>
          <div class="${TW.statsCard}">
            <strong>${escapeHtml(String(detail.failure_count))}</strong>
            <span>失败</span>
          </div>
        </div>
        <div class="${TW.notice}">
          <h4>错误摘要</h4>
          <p>${escapeHtml(detail.error_summary || "当前没有错误摘要。")}</p>
        </div>
      </article>
      <article class="${TW.card} ${TW.cardWide}">
        <h3>逐条处理明细</h3>
        ${
          items.length === 0
            ? `<div class="${TW.notice}"><h4>暂无处理明细</h4><p>任务尚未执行，或当前没有结构化明细。</p></div>`
            : `
              <div class="${TW.tableWrapper}">
                <table class="${TW.dataTable}">
                  <thead>
                    <tr>
                      <th class="${TW.th}">时间</th>
                      <th class="${TW.th}">来源项</th>
                      <th class="${TW.th}">动作</th>
                      <th class="${TW.th}">结果</th>
                      <th class="${TW.th}">定位信息</th>
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

function renderTaskRow(item) {
  return `
    <tr>
      <td class="${TW.td}">
        <div class="${TW.tableTitle}">
          <strong>#${escapeHtml(String(item.id))}</strong>
          <span>${escapeHtml(item.task_type)} / ${escapeHtml(item.trigger_type)}</span>
        </div>
      </td>
      <td class="${TW.td}">
        <div class="${TW.stackedCopy}">
          <span class="${statusBadgeClasses(item.task_status)}">${escapeHtml(item.task_status)}</span>
          <span class="${TW.mutedInline}">${escapeHtml(item.started_at_utc || "未开始")}</span>
        </div>
      </td>
      <td class="${TW.td}">
        <div class="${TW.stackedCopy}">
          <span>${escapeHtml(item.source_type)} / ${escapeHtml(item.market_code || "无地区")}</span>
          <span class="${TW.mutedInline}">${escapeHtml(item.date_from || "无")} ~ ${escapeHtml(item.date_to || "无")}</span>
        </div>
      </td>
      <td class="${TW.td}">
        <div class="${TW.stackedCopy}">
          <span>成功 ${escapeHtml(String(item.success_count))}</span>
          <span class="${TW.mutedInline}">重复 ${escapeHtml(String(item.duplicate_count))} / 失败 ${escapeHtml(String(item.failure_count))}</span>
        </div>
      </td>
      <td class="${TW.td}">${escapeHtml(item.error_summary || "无")}</td>
      <td class="${TW.td}">
        <div class="${TW.btnRow}">
          <a class="${TW.inlineLink}" href="/admin/tasks/${escapeHtml(String(item.id))}">详情</a>
          <a class="${TW.inlineLink}" href="/admin/logs?task_id=${escapeHtml(String(item.id))}">日志</a>
          ${renderConsumeButton(item)}
          ${renderRetryButton(item)}
        </div>
      </td>
    </tr>
  `;
}

function renderRetryButton(item) {
  if (item.task_status !== "failed" && item.task_status !== "partially_failed") {
    return "";
  }
  return `<button class="${TW.miniBtn}" type="button" data-task-retry="${escapeHtml(String(item.id))}">重试</button>`;
}

function renderConsumeButton(item) {
  if (item.task_status !== "queued") {
    return "";
  }
  return `<button class="${TW.miniBtn}" type="button" data-task-consume="${escapeHtml(String(item.id))}">立即执行</button>`;
}

function renderTaskItemRow(item) {
  return `
    <tr>
      <td class="${TW.td}">${escapeHtml(item.occurred_at_utc)}</td>
      <td class="${TW.td}"><code>${escapeHtml(item.source_item_key || "-")}</code></td>
      <td class="${TW.td}">${escapeHtml(item.action_name)}</td>
      <td class="${TW.td}">${escapeHtml(item.result_status)}</td>
      <td class="${TW.td}"><pre>${escapeHtml(JSON.stringify({
        dedupe_hit_type: item.dedupe_hit_type,
        db_write_result: item.db_write_result,
        file_write_result: item.file_write_result,
        failure_reason: item.failure_reason,
      }, null, 2))}</pre></td>
    </tr>
  `;
}
