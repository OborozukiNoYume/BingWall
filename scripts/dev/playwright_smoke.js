let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (error) {
  console.error("Missing Playwright module. Run `npm install --no-save playwright` first.");
  if (error && error.stack) {
    console.error(error.stack);
  }
  process.exit(1);
}

const baseUrl = process.env.BINGWALL_BROWSER_BASE_URL || "http://127.0.0.1:30003";
const headless = (process.env.BINGWALL_BROWSER_HEADLESS || "true").toLowerCase() !== "false";
const adminUsername = process.env.BINGWALL_ADMIN_USERNAME || "";
const adminPassword = process.env.BINGWALL_ADMIN_PASSWORD || "";

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function logStep(step, detail) {
  const suffix = detail ? `: ${detail}` : "";
  console.log(`[browser-smoke] ${step}${suffix}`);
}

async function waitForFirstDetailLink(page) {
  const detailLink = page.locator('#wallpaper-list-results a[href^="/wallpapers/"]').first();
  await detailLink.waitFor({ state: "visible", timeout: 10000 });
  return detailLink;
}

async function run() {
  logStep("launch", `${baseUrl} headless=${headless}`);
  const browser = await chromium.launch({ headless });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });

  page.on("pageerror", (error) => {
    console.error("[browser-smoke] pageerror", error);
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      console.error("[browser-smoke] console.error", message.text());
    }
  });

  try {
    logStep("home", "open public home page");
    await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
    assert((await page.title()) === "BingWall | 首页", "Unexpected home page title.");
    await page.locator("[data-brand-mark]").waitFor({ state: "visible" });
    await page.locator("text=今日壁纸 API").waitFor({ state: "visible" });

    logStep("list", "open public list page");
    await page.goto(`${baseUrl}/wallpapers`, { waitUntil: "networkidle" });
    await page.locator("#market-code").waitFor({ state: "visible" });

    logStep("list", "apply en-US market filter");
    await page.selectOption("#market-code", "en-US");
    await Promise.all([
      page.waitForResponse(
        (response) =>
          response.url().includes("/api/public/wallpapers") && response.request().method() === "GET",
      ),
      page.locator('#wallpaper-filter-form button[type="submit"]').click(),
    ]);
    await page.waitForURL(/market_code=en-US/);

    let detailLink;
    const filteredLinks = await page.locator('#wallpaper-list-results a[href^="/wallpapers/"]').count();
    if (filteredLinks > 0) {
      detailLink = page.locator('#wallpaper-list-results a[href^="/wallpapers/"]').first();
    } else {
      logStep("list", "en-US has no visible results, falling back to the unfiltered list");
      await page.goto(`${baseUrl}/wallpapers`, { waitUntil: "networkidle" });
      detailLink = await waitForFirstDetailLink(page);
    }

    logStep("detail", "open first wallpaper detail page");
    await Promise.all([
      page.waitForURL(/\/wallpapers\/\d+$/),
      detailLink.click(),
    ]);
    await page.waitForLoadState("networkidle");
    assert((await page.title()) === "BingWall | 壁纸详情", "Unexpected detail page title.");
    const imageUrl = await page.locator("img").first().getAttribute("src");
    assert(imageUrl && imageUrl.startsWith("/images/"), "Detail page did not expose a public image URL.");

    logStep("admin", "open admin login page");
    await page.goto(`${baseUrl}/admin/login`, { waitUntil: "networkidle" });
    assert((await page.title()) === "BingWall Admin | 登录", "Unexpected admin login page title.");
    await page.locator("#admin-login-form").waitFor({ state: "visible" });

    if (adminUsername && adminPassword) {
      logStep("admin", "submit admin login form");
      await page.fill("#username", adminUsername);
      await page.fill("#password", adminPassword);
      await Promise.all([
        page.waitForURL(/\/admin\/wallpapers$/),
        page.locator('#admin-login-form button[type="submit"]').click(),
      ]);
      await page.waitForLoadState("networkidle");
      await page.locator("text=内容管理").first().waitFor({ state: "visible" });
    } else {
      logStep(
        "admin",
        "skip authenticated admin flow because BINGWALL_ADMIN_USERNAME / BINGWALL_ADMIN_PASSWORD are not set",
      );
    }

    const report = {
      ok: true,
      base_url: baseUrl,
      headless,
      authenticated_admin_check: Boolean(adminUsername && adminPassword),
    };
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error("[browser-smoke] failed");
  if (error && error.stack) {
    console.error(error.stack);
  } else {
    console.error(String(error));
  }
  process.exit(1);
});
