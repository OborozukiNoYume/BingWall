"use strict";

const DEFAULT_BASE_URL = "http://127.0.0.1:30003";

function isHeadlessEnabled(rawValue) {
  return (rawValue || "true").toLowerCase() !== "false";
}

function getBrowserSmokeConfig(env = process.env) {
  return {
    baseUrl: env.BINGWALL_BROWSER_BASE_URL || env.BINGWALL_APP_BASE_URL || DEFAULT_BASE_URL,
    headless: isHeadlessEnabled(env.BINGWALL_BROWSER_HEADLESS),
    adminUsername: env.BINGWALL_ADMIN_USERNAME || "",
    adminPassword: env.BINGWALL_ADMIN_PASSWORD || "",
  };
}

module.exports = {
  DEFAULT_BASE_URL,
  getBrowserSmokeConfig,
  isHeadlessEnabled,
};
