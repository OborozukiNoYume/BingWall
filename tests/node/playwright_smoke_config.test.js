"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_BASE_URL,
  getBrowserSmokeConfig,
  isHeadlessEnabled,
} = require("../../scripts/dev/playwright_smoke_config");

test("uses documented defaults when browser env vars are absent", () => {
  const config = getBrowserSmokeConfig({});

  assert.equal(config.baseUrl, DEFAULT_BASE_URL);
  assert.equal(config.headless, true);
  assert.equal(config.adminUsername, "");
  assert.equal(config.adminPassword, "");
});

test("prefers application base url when browser base url is unset", () => {
  const config = getBrowserSmokeConfig({
    BINGWALL_APP_BASE_URL: "http://127.0.0.1:38080",
  });

  assert.equal(config.baseUrl, "http://127.0.0.1:38080");
});

test("browser-specific base url overrides application base url", () => {
  const config = getBrowserSmokeConfig({
    BINGWALL_APP_BASE_URL: "http://127.0.0.1:38080",
    BINGWALL_BROWSER_BASE_URL: "http://127.0.0.1:18080",
  });

  assert.equal(config.baseUrl, "http://127.0.0.1:18080");
});

test("parses headless toggle and admin credentials", () => {
  const config = getBrowserSmokeConfig({
    BINGWALL_BROWSER_HEADLESS: "false",
    BINGWALL_ADMIN_USERNAME: "admin",
    BINGWALL_ADMIN_PASSWORD: "secret",
  });

  assert.equal(config.headless, false);
  assert.equal(config.adminUsername, "admin");
  assert.equal(config.adminPassword, "secret");
});

test("treats any value other than false as headless enabled", () => {
  assert.equal(isHeadlessEnabled(undefined), true);
  assert.equal(isHeadlessEnabled("TRUE"), true);
  assert.equal(isHeadlessEnabled("0"), true);
  assert.equal(isHeadlessEnabled("false"), false);
});
