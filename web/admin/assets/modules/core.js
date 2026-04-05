export const adminRoot = document.querySelector("#admin-root");
const body = document.body;

export const pageName = body.dataset.page;
export const wallpaperId = body.dataset.wallpaperId;
export const taskId = body.dataset.taskId;
export const sessionCopyNode = document.querySelector("[data-admin-session]");
export const logoutButton = document.querySelector("[data-admin-logout]");

const SESSION_STORAGE_KEY = "bingwall_admin_session";

export const TW = {
  panel: "border border-slate-200/60 rounded-2xl bg-slate-50 p-6 grid gap-5 shadow-sm",
  card: "border border-slate-200/60 rounded-xl bg-slate-50 grid gap-4 p-6 shadow-sm",
  cardWide: "col-span-full",
  form: "grid gap-4",
  filterGrid: "grid grid-cols-2 sm:grid-cols-3 gap-3",
  field: "grid gap-1",
  label: "text-sm font-medium",
  input: "w-full border border-slate-200 rounded-xl bg-white px-3 py-2.5 text-sm focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none",
  primaryBtn: "inline-flex items-center justify-center h-10 rounded-full bg-slate-800 text-white px-5 text-sm cursor-pointer border-0 hover:bg-slate-700 hover:shadow-sm active:scale-[0.98]",
  ghostBtn: "inline-flex items-center justify-center h-10 rounded-full border border-slate-200 bg-transparent px-4 text-sm cursor-pointer text-slate-600 hover:bg-slate-50 hover:border-slate-300 no-underline active:scale-[0.98]",
  miniBtn: "inline-flex items-center justify-center h-8 rounded-full border border-slate-200 bg-transparent px-3 text-xs cursor-pointer hover:bg-slate-50 hover:border-slate-300 active:scale-[0.97]",
  notice: "border border-slate-200/60 rounded-xl bg-slate-50 p-4 grid gap-1 shadow-sm",
  noticeWarn: "border border-orange-300 bg-orange-50 p-4 grid gap-1 shadow-sm",
  panelHead: "flex items-start justify-between gap-4 mb-5",
  detailGrid: "grid grid-cols-1 lg:grid-cols-2 gap-4",
  tableCard: "overflow-hidden border border-slate-200/60 rounded-xl mt-4 shadow-sm",
  tableWrapper: "overflow-x-auto",
  dataTable: "w-full border-collapse text-sm",
  th: "border-b border-slate-200 bg-slate-100 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-600",
  td: "border-b border-slate-100 px-4 py-3 align-top hover:bg-slate-50/50",
  btnRow: "flex flex-wrap gap-3",
  metaPill: "inline-flex items-center h-7 rounded-full bg-slate-100 px-3 text-sm font-medium text-slate-600",
  stackedCopy: "grid gap-0.5",
  tableTitle: "grid gap-0.5",
  inlineLink: "text-sm text-amber-600 hover:underline",
  statsGrid: "grid grid-cols-2 sm:grid-cols-3 gap-3 mt-4",
  statsCard: "border border-slate-200/60 rounded-xl p-4 grid gap-1 bg-white text-center shadow-sm hover:shadow-md transition-shadow duration-200",
  tagChipGrid: "grid grid-cols-2 gap-3",
  tagChip: "flex items-start gap-2 border border-slate-200/60 rounded-xl bg-white p-3 shadow-sm hover:shadow-md hover:border-slate-300 transition-all duration-200",
  checkboxRow: "inline-flex items-center gap-2 text-sm text-slate-600",
  previewFrame: "grid place-items-center min-h-[260px] overflow-hidden border border-slate-200/60 rounded-xl bg-slate-100 shadow-sm",
  eyebrow: "text-xs font-semibold uppercase tracking-widest text-amber-600 mb-2",
  mutedCopy: "text-sm text-slate-500 mt-1",
  mutedInline: "text-sm text-slate-500",
};

export function statusBadgeClasses(status) {
  const base = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold";
  const map = {
    enabled: "bg-emerald-50 text-emerald-700",
    disabled: "bg-amber-50 text-amber-700",
    deleted: "bg-rose-50 text-rose-700",
    draft: "bg-slate-100 text-slate-600",
    ready: "bg-emerald-50 text-emerald-700",
    pending: "bg-amber-50 text-amber-700",
    failed: "bg-rose-50 text-rose-700",
    queued: "bg-blue-50 text-blue-700",
    running: "bg-sky-50 text-sky-700",
    succeeded: "bg-emerald-50 text-emerald-700",
    partially_failed: "bg-orange-50 text-orange-700",
  };
  return `${base} ${map[status] || "bg-slate-100 text-slate-600"}`;
}

export function readWallpaperListState() {
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

export function readTaskListState() {
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

export function readTagState() {
  const params = new URLSearchParams(window.location.search);
  return {
    status: params.get("status") || "",
    tag_category: params.get("tag_category") || "",
  };
}

export function readDownloadStatsState() {
  const params = new URLSearchParams(window.location.search);
  return {
    days: params.get("days") || "7",
    top_limit: params.get("top_limit") || "5",
  };
}

export function readLogState() {
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

export function readAuditState() {
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

export function buildWallpaperListParams(state) {
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

export function buildTaskParams(state) {
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

export function buildTagParams(state) {
  const params = new URLSearchParams();
  setOptionalParam(params, "status", state.status);
  setOptionalParam(params, "tag_category", state.tag_category);
  return params;
}

export function buildDownloadStatsParams(state) {
  const params = new URLSearchParams();
  params.set("days", state.days || "7");
  params.set("top_limit", state.top_limit || "5");
  return params;
}

export function buildLogParams(state) {
  const params = new URLSearchParams();
  params.set("page", state.page || "1");
  params.set("page_size", state.page_size || "20");
  setOptionalParam(params, "task_id", state.task_id);
  setOptionalParam(params, "error_type", state.error_type);
  setOptionalParam(params, "started_from_utc", toUtcQueryValue(state.started_from_utc));
  setOptionalParam(params, "started_to_utc", toUtcQueryValue(state.started_to_utc));
  return params;
}

export function buildAuditParams(state) {
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

export function renderDetailRow(label, value) {
  return `
    <div>
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(value)}</dd>
    </div>
  `;
}

export function renderPaginationLinks(basePath, state, totalPages) {
  if (!totalPages || totalPages <= 1) {
    return "";
  }

  const currentPage = Number(state.page || "1");
  const links = [];
  if (currentPage > 1) {
    links.push(`<a class="${TW.ghostBtn}" href="${buildPageHref(basePath, state, currentPage - 1)}">上一页</a>`);
  }
  if (currentPage < totalPages) {
    links.push(`<a class="${TW.ghostBtn}" href="${buildPageHref(basePath, state, currentPage + 1)}">下一页</a>`);
  }
  return links.join("");
}

export function assignFormValue(form, name, value) {
  const field = form.elements.namedItem(name);
  if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement) {
    field.value = value || "";
  }
}

export function setLoadingState(message) {
  adminRoot.innerHTML = `
    <div class="${TW.notice}">
      <h2>正在加载</h2>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
}

export function setNotice(node, title, copy) {
  node.innerHTML = `
    <div class="${TW.notice}">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(copy)}</p>
    </div>
  `;
}

export function handleAdminError(error) {
  console.error(error);
  if (error instanceof ApiError && error.status === 401) {
    clearSession();
    redirectToLogin();
    return;
  }
  const message = error instanceof ApiError ? error.message : "后台接口暂时不可用，请稍后重试。";
  adminRoot.innerHTML = `
    <div class="${TW.noticeWarn}">
      <h2>服务繁忙</h2>
      <p>${escapeHtml(message)}</p>
      <div class="${TW.btnRow}">
        <a class="${TW.ghostBtn}" href="/admin/tasks">返回采集任务</a>
        <a class="${TW.ghostBtn}" href="/admin/wallpapers">返回内容管理</a>
      </div>
    </div>
  `;
}

export async function fetchAdmin(url, options = {}) {
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

export function loadSession() {
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

export function storeSession(response) {
  const session = {
    session_token: response.session_token,
    expires_at_utc: response.expires_at_utc,
    username: response.user.username,
    role_name: response.user.role_name,
  };
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearSession() {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
  updateSessionCopy("当前未登录后台。");
}

export function updateSessionCopy(message) {
  if (sessionCopyNode instanceof HTMLElement) {
    sessionCopyNode.textContent = message;
  }
}

export function redirectToLogin() {
  redirectTo("/admin/login");
}

export function redirectTo(url) {
  window.location.assign(url);
}

export function stringValue(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function formatResolution(width, height) {
  if (!width || !height) {
    return "未提供";
  }
  return `${width} x ${height}`;
}

export function formatBytes(value) {
  if (!value) {
    return "未提供";
  }
  return `${value} bytes`;
}

export function formatBoolean(value) {
  return value ? "true" : "false";
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
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

function setOptionalParam(params, key, value) {
  if (value) {
    params.set(key, value);
  }
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
