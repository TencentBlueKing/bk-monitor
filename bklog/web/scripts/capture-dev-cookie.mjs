/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { existsSync, lstatSync, mkdirSync, readFileSync, readlinkSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, '..');
const require = createRequire(import.meta.url);
const timeoutMs = 5 * 60 * 1000;

export function resolveWritableTarget(filePath) {
  let current = resolve(filePath);
  const seen = new Set();
  while (true) {
    if (seen.has(current)) break;
    seen.add(current);
    try {
      const stat = lstatSync(current);
      if (!stat.isSymbolicLink()) break;
      current = resolve(dirname(current), readlinkSync(current));
    } catch {
      break;
    }
  }
  mkdirSync(dirname(current), { recursive: true });
  return current;
}

export function extractCsrfToken(cookies, capturedHeader = '') {
  if (capturedHeader) return capturedHeader.trim();
  const preferred =
    cookies.find(cookie => cookie.name === 'bklog_csrftoken' && cookie.value)
    || cookies.find(cookie => cookie.name === 'csrftoken' && cookie.value)
    || cookies.find(cookie => /csrf/i.test(cookie.name) && cookie.value);
  if (!preferred?.value) return '';
  try {
    return decodeURIComponent(preferred.value);
  } catch {
    return preferred.value;
  }
}

export function formatCookieHeader(cookies) {
  const seen = new Set();
  const pairs = [];
  for (const cookie of cookies) {
    if (!cookie?.name || seen.has(cookie.name)) continue;
    seen.add(cookie.name);
    pairs.push(`${cookie.name}=${cookie.value ?? ''}`);
  }
  return pairs.join('; ');
}

export function upsertEnvAssignment(content, key, value) {
  const eol = content.includes('\r\n') ? '\r\n' : '\n';
  const lines = content ? content.split(/\r?\n/) : [];
  if (lines.length && lines[lines.length - 1] === '') lines.pop();
  const pattern = new RegExp(`^\\s*${key}\\s*=`);
  let replaced = false;
  const next = lines.map(line => {
    if (!replaced && pattern.test(line)) {
      replaced = true;
      return `${key}=${value}`;
    }
    return line;
  });
  if (!replaced) next.push(`${key}=${value}`);
  return `${next.join(eol)}${eol}`;
}

export function writeCookieAndCsrf({ cookiePath, envPath, cookieHeader, csrfToken }) {
  const cookieTarget = resolveWritableTarget(cookiePath);
  writeFileSync(cookieTarget, `${cookieHeader}\n`, { mode: 0o600 });
  let csrfUpdated = false;
  if (envPath && csrfToken) {
    const envTarget = resolveWritableTarget(envPath);
    const previous = existsSync(envTarget) ? readFileSync(envTarget, 'utf8') : '';
    const updated = upsertEnvAssignment(previous, 'BKLOG_CSRF_TOKEN', csrfToken);
    writeFileSync(envTarget, updated, { mode: 0o600 });
    csrfUpdated = true;
  }
  return { csrfUpdated };
}

async function openBrowser() {
  try {
    return await chromium.launch({ headless: false, channel: 'chrome' });
  } catch {
    return await chromium.launch({ headless: false });
  }
}

async function isAuthenticated(context, targetUrl) {
  const base = targetUrl.href.endsWith('/') ? targetUrl.href : `${targetUrl.href}/`;
  const checkUrl = new URL('api/v1/meta/index_html_environment/', base).toString();
  try {
    const response = await context.request.get(checkUrl, {
      maxRedirects: 0,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      timeout: 10_000,
    });
    if (response.status() !== 200) return false;
    const contentType = String(response.headers()['content-type'] || '');
    return contentType.includes('json');
  } catch {
    return false;
  }
}

async function main() {
  const { loadLocalEnv } = require(resolve(webRoot, 'dev-env.js'));
  const defaultEnvPath = resolve(webRoot, '.env.local');
  const defaultCookiePath = resolve(webRoot, '.cookie');
  loadLocalEnv(defaultEnvPath);

  const target = (process.argv[2] || process.env.BKLOG_DEV_PROXY_URL || '').trim();
  const cookiePath = process.argv[3] || defaultCookiePath;
  const envPath = process.argv[4] || defaultEnvPath;

  if (!target || !/^https?:\/\//.test(target) || !cookiePath) {
    console.error('[dev-cookie] 缺少有效的 BKLOG_DEV_PROXY_URL 或本地 .cookie 路径');
    process.exit(1);
  }

  const targetUrl = new URL(target);
  const browser = await openBrowser();
  let capturedCsrfHeader = '';
  let closedByUser = false;

  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    page.on('close', () => {
      closedByUser = true;
    });
    page.on('request', req => {
      try {
        if (new URL(req.url()).origin !== targetUrl.origin) return;
        const header = req.headers()['x-csrftoken'];
        if (header) capturedCsrfHeader = header;
      } catch {
        // Ignore malformed request URLs.
      }
    });

    await page.goto(targetUrl.href, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline && !closedByUser && !page.isClosed()) {
      let currentUrl;
      try {
        currentUrl = new URL(page.url());
      } catch {
        currentUrl = null;
      }
      const onTargetHost = currentUrl?.hostname === targetUrl.hostname;
      const onLoginPath = Boolean(currentUrl && /\/login\b|\/plain\b/i.test(currentUrl.pathname));

      if (onTargetHost && !onLoginPath && (await isAuthenticated(context, targetUrl))) {
        let cookies = await context.cookies(targetUrl.origin);
        let csrfToken = extractCsrfToken(cookies, capturedCsrfHeader);
        if (!csrfToken) {
          await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {});
          cookies = await context.cookies(targetUrl.origin);
          csrfToken = extractCsrfToken(cookies, capturedCsrfHeader);
        }
        const cookieHeader = formatCookieHeader(cookies);
        if (cookieHeader) {
          const { csrfUpdated } = writeCookieAndCsrf({ cookiePath, envPath, cookieHeader, csrfToken });
          console.info(
            `[dev-cookie] 登录完成，已保存 ${cookies.length} 项 Cookie 到 .cookie${
              csrfUpdated ? '，并更新 .env.local 中的 BKLOG_CSRF_TOKEN' : '（未检测到 csrftoken）'
            }`,
          );
          process.exitCode = 0;
          return;
        }
      }
      await page.waitForTimeout(1000).catch(() => {});
    }

    console.error(closedByUser ? '[dev-cookie] 浏览器窗口已关闭，未完成登录' : '[dev-cookie] 等待登录超时');
    process.exitCode = 1;
  } finally {
    await browser.close().catch(() => {});
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
