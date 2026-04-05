import { adminRoot, loadSession, pageName, taskId, updateSessionCopy, wallpaperId } from "./modules/core.js";
import { bindLogoutButton, renderChangePasswordPage, renderLoginPage } from "./pages/auth.js";
import { renderDownloadStatsPage, renderAuditPage, renderLogPage } from "./pages/observability.js";
import { renderTagManagementPage } from "./pages/tags.js";
import { renderTaskDetailPage, renderTaskListPage } from "./pages/tasks.js";
import { renderWallpaperDetailPage, renderWallpaperListPage } from "./pages/wallpapers.js";

document.addEventListener("DOMContentLoaded", async () => {
  bindLogoutButton();

  if (!(adminRoot instanceof HTMLElement)) {
    return;
  }

  if (pageName === "admin-login") {
    renderLoginPage();
    const session = loadSession();
    updateSessionCopy(session ? `当前已保存后台会话，账号：${session.username}` : "当前未登录后台。");
    return;
  }

  const session = loadSession();
  if (!session) {
    window.location.assign("/admin/login");
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
