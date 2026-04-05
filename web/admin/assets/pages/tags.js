import {
  adminRoot,
  ApiError,
  assignFormValue,
  buildTagParams,
  escapeHtml,
  fetchAdmin,
  handleAdminError,
  readTagState,
  redirectTo,
  setLoadingState,
  setNotice,
  statusBadgeClasses,
  stringValue,
  TW,
} from "../modules/core.js";

export async function renderTagManagementPage(session) {
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
    <div class="${TW.panelHead}">
      <div>
        <h2>标签维护</h2>
        <p class="${TW.mutedCopy}">标签定义统一保存在 <code>tags</code> 表中，内容绑定保存在 <code>wallpaper_tags</code> 表中。</p>
      </div>
      <p class="${TW.metaPill}">共 ${items.length} 个标签</p>
    </div>
    <section class="${TW.detailGrid}">
      <article class="${TW.card}">
        <h3>创建 / 更新标签</h3>
        <form class="${TW.form}" id="tag-form">
          <input type="hidden" name="tag_id" />
          <div class="${TW.filterGrid}">
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-key">稳定键</label>
              <input class="${TW.input}" id="tag-key" name="tag_key" type="text" placeholder="例如 theme_landscape" required />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-name">标签名</label>
              <input class="${TW.input}" id="tag-name" name="tag_name" type="text" placeholder="例如 风景" required />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-category">分类</label>
              <input class="${TW.input}" id="tag-category" name="tag_category" type="text" placeholder="例如 theme" />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-status">状态</label>
              <select class="${TW.input}" id="tag-status" name="status">
                <option value="enabled">enabled</option>
                <option value="disabled">disabled</option>
              </select>
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-sort-weight">排序权重</label>
              <input class="${TW.input}" id="tag-sort-weight" name="sort_weight" type="number" value="0" />
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-operator-reason">操作原因</label>
              <input class="${TW.input}" id="tag-operator-reason" name="operator_reason" type="text" placeholder="例如：新增公开主题标签" required />
            </div>
          </div>
          <div class="${TW.btnRow}">
            <button class="${TW.primaryBtn}" type="submit">保存标签</button>
            <button class="${TW.ghostBtn}" id="reset-tag-form" type="button">清空表单</button>
          </div>
        </form>
        <div id="tag-form-feedback"></div>
      </article>
      <article class="${TW.card}">
        <h3>标签筛选</h3>
        <form class="${TW.form}" id="tag-filter-form">
          <div class="${TW.filterGrid}">
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-filter-status">状态</label>
              <select class="${TW.input}" id="tag-filter-status" name="status">
                <option value="">全部</option>
                <option value="enabled">enabled</option>
                <option value="disabled">disabled</option>
              </select>
            </div>
            <div class="${TW.field}">
              <label class="${TW.label}" for="tag-filter-category">分类</label>
              <input class="${TW.input}" id="tag-filter-category" name="tag_category" type="text" placeholder="例如 theme" />
            </div>
          </div>
          <div class="${TW.btnRow}">
            <button class="${TW.primaryBtn}" type="submit">刷新标签列表</button>
            <button class="${TW.ghostBtn}" id="reset-tag-filters" type="button">重置筛选</button>
          </div>
        </form>
      </article>
    </section>
    <section class="${TW.tableCard}">
      <div class="${TW.tableWrapper}">
        <table class="${TW.dataTable}">
          <thead>
            <tr>
              <th class="${TW.th}">标签</th>
              <th class="${TW.th}">状态</th>
              <th class="${TW.th}">分类</th>
              <th class="${TW.th}">排序</th>
              <th class="${TW.th}">内容数</th>
              <th class="${TW.th}">操作</th>
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
        <td colspan="6" class="${TW.td}">
          <div class="${TW.notice}">
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

function renderTagRow(item) {
  return `
    <tr>
      <td class="${TW.td}">
        <div class="${TW.tableTitle}">
          <strong>${escapeHtml(item.tag_name)}</strong>
          <span><code>${escapeHtml(item.tag_key)}</code></span>
        </div>
      </td>
      <td class="${TW.td}"><span class="${statusBadgeClasses(item.status)}">${escapeHtml(item.status)}</span></td>
      <td class="${TW.td}">${escapeHtml(item.tag_category || "未分类")}</td>
      <td class="${TW.td}">${escapeHtml(String(item.sort_weight))}</td>
      <td class="${TW.td}">${escapeHtml(String(item.wallpaper_count))}</td>
      <td class="${TW.td}">
        <div class="${TW.btnRow}">
          <button class="${TW.miniBtn}" type="button" data-tag-edit="${escapeHtml(String(item.id))}">编辑</button>
          <a class="${TW.inlineLink}" href="/admin/audit-logs?target_type=tag&target_id=${escapeHtml(String(item.id))}">审计</a>
        </div>
      </td>
    </tr>
  `;
}
