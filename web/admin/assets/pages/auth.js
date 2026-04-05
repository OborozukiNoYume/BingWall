import {
  adminRoot,
  ApiError,
  clearSession,
  fetchAdmin,
  loadSession,
  logoutButton,
  redirectTo,
  redirectToLogin,
  setNotice,
  storeSession,
  stringValue,
  TW,
} from "../modules/core.js";

export function bindLogoutButton() {
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

export function renderLoginPage() {
  adminRoot.innerHTML = `
    <section class="${TW.panel}">
      <div>
        <p class="${TW.eyebrow}">后台认证</p>
        <h2>登录后再进行内容管理</h2>
        <p class="${TW.mutedCopy}">登录成功后，浏览器只保存会话令牌；后台页面不会直接读取数据库文件。</p>
      </div>
      <form class="${TW.form}" id="admin-login-form">
        <div class="${TW.field}">
          <label class="${TW.label}" for="username">用户名</label>
          <input class="${TW.input}" id="username" name="username" type="text" autocomplete="username" required />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="password">密码</label>
          <input class="${TW.input}" id="password" name="password" type="password" autocomplete="current-password" required />
        </div>
        <div class="${TW.btnRow}">
          <button class="${TW.primaryBtn}" type="submit">登录后台</button>
        </div>
      </form>
      <div class="${TW.notice}" id="login-feedback">
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

export function renderChangePasswordPage(session) {
  adminRoot.innerHTML = `
    <section class="${TW.panel}">
      <div>
        <p class="${TW.eyebrow}">账号安全</p>
        <h2>修改后台密码</h2>
        <p class="${TW.mutedCopy}">提交成功后，当前账号的后台会话会立即失效，需使用新密码重新登录。</p>
      </div>
      <form class="${TW.form}" id="admin-change-password-form">
        <div class="${TW.field}">
          <label class="${TW.label}" for="current-password">当前密码</label>
          <input class="${TW.input}"
            id="current-password"
            name="current_password"
            type="password"
            autocomplete="current-password"
            required
          />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="new-password">新密码</label>
          <input class="${TW.input}"
            id="new-password"
            name="new_password"
            type="password"
            autocomplete="new-password"
            required
          />
        </div>
        <div class="${TW.field}">
          <label class="${TW.label}" for="confirm-new-password">确认新密码</label>
          <input class="${TW.input}"
            id="confirm-new-password"
            name="confirm_new_password"
            type="password"
            autocomplete="new-password"
            required
          />
        </div>
        <div class="${TW.btnRow}">
          <button class="${TW.primaryBtn}" type="submit">保存新密码</button>
          <a class="${TW.ghostBtn}" href="/admin/wallpapers">返回内容管理</a>
        </div>
      </form>
      <div class="${TW.notice}" id="change-password-feedback">
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
        clearSession();
        redirectToLogin();
        return;
      }
      console.error(error);
      const message = error instanceof ApiError ? error.message : "修改密码失败，请稍后重试。";
      setNotice(feedback, "修改失败", message);
    }
  });
}
