/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { spawn } from 'node:child_process';
import { existsSync, readFileSync, watchFile } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig, type Plugin, type ProxyOptions, type ViteDevServer } from 'vite';

const require = createRequire(import.meta.url);
const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const { loadLocalEnv, reloadLocalEnv, devProxyUrl, allowedHosts } = require(resolve(webRoot, 'dev-env.js'));
const settingsFile = resolve(webRoot, 'packages/web-v2/local.settings.js');
const envFile = resolve(webRoot, '.env.local');
const cookieFile = resolve(webRoot, '.cookie');
const cookieCaptureScript = resolve(webRoot, 'scripts/capture-dev-cookie.mjs');

if (process.env.NODE_ENV !== 'production') loadLocalEnv(envFile);

function readCookieFile() {
  if (!existsSync(cookieFile)) return '';
  return readFileSync(cookieFile, 'utf8').trim();
}

function csrfFromCookie(cookie: string) {
  const matched = cookie.match(/(?:^|;\s*)(?:bklog_csrftoken|csrftoken)=([^;]*)/i);
  if (!matched?.[1]) return '';
  try {
    return decodeURIComponent(matched[1]);
  } catch {
    return matched[1];
  }
}

function loadLocalSettings() {
  if (!existsSync(settingsFile)) {
    console.warn('[web-v3] 未找到 packages/web-v2/local.settings.js，将按 .env.local 与 .cookie 代理 /api。');
    return {};
  }
  if (!existsSync(cookieFile)) {
    console.warn('[web-v3] 未找到 bklog/web/.cookie，/api 代理不会带登录头。登录 Cookie 放在该文件，不要写入仓库。');
  }
  const previous = process.cwd();
  try {
    process.chdir(webRoot);
    return require(settingsFile);
  } catch (error) {
    console.warn(`[web-v3] 读取 local.settings.js 失败，/api 代理不会带登录头：${error instanceof Error ? error.message : error}`);
    return {};
  } finally {
    process.chdir(previous);
  }
}

const localSettings = process.env.NODE_ENV === 'production' ? {} : loadLocalSettings();
const proxyRule = localSettings.proxy?.[0] ?? {};
const proxyTarget = process.env.BKLOG_DEV_PROXY_URL || proxyRule.target || localSettings.devProxyUrl || devProxyUrl();
const proxyContexts = Array.isArray(proxyRule.context) && proxyRule.context.length ? proxyRule.context : ['/api'];

let liveCookie = process.env.NODE_ENV === 'production' ? '' : readCookieFile() || proxyRule.headers?.Cookie || '';
let liveCsrfToken =
  process.env.NODE_ENV === 'production'
    ? ''
    : process.env.BKLOG_CSRF_TOKEN || csrfFromCookie(liveCookie) || proxyRule.headers?.['X-CSRFToken'] || '';

const targetOrigin = /^https?:\/\//.test(String(proxyTarget)) ? new URL(String(proxyTarget)) : undefined;
const proxyHeaders: Record<string, string> = {
  ...(proxyRule.headers || {}),
};
if (targetOrigin) {
  proxyHeaders.host = targetOrigin.host;
  proxyHeaders.referer = targetOrigin.origin;
}
if (liveCookie) proxyHeaders.Cookie = liveCookie;
else delete proxyHeaders.Cookie;
if (liveCsrfToken) proxyHeaders['X-CSRFToken'] = liveCsrfToken;

let devServer: ViteDevServer | undefined;
let localFileWatchStarted = false;
let devCookieCapture: ReturnType<typeof spawn> | undefined;
let captureCooldownUntil = 0;

function isAuthExpiredResponse(status: number, location: string) {
  if (status === 401) return true;
  if (status !== 301 && status !== 302) return false;
  if (!location) return false;
  try {
    const resolved = new URL(location, proxyTarget);
    if (resolved.hostname.startsWith('login.')) return true;
    if (/\/login\b|\/plain\b/i.test(resolved.pathname)) return true;
    return Boolean(targetOrigin && resolved.hostname !== targetOrigin.hostname && /sso|auth|login/i.test(resolved.hostname));
  } catch {
    return false;
  }
}

function syncProxyHeaders(server: ViteDevServer | undefined, cookie: string, csrf: string) {
  liveCookie = cookie;
  liveCsrfToken = csrf;
  const rules = server?.config.server.proxy;
  if (!rules) return;
  for (const rule of Object.values(rules)) {
    if (!rule || typeof rule === 'string') continue;
    const headers = ((rule as ProxyOptions).headers ||= {});
    if (liveCookie) headers.Cookie = liveCookie;
    else delete headers.Cookie;
    if (liveCsrfToken) headers['X-CSRFToken'] = liveCsrfToken;
  }
}

function captureDevCookie() {
  if (process.env.NODE_ENV === 'production' || devCookieCapture) return;
  if (Date.now() < captureCooldownUntil) return;
  const captureUrl = process.env.BKLOG_DEV_PROXY_URL || String(proxyTarget || '');
  if (!/^https?:\/\//.test(captureUrl)) return;
  console.info('[web-v3] 登录已失效，正在通过 Playwright 打开 BKLOG_DEV_PROXY_URL 完成授权');
  devCookieCapture = spawn(process.execPath, [cookieCaptureScript, captureUrl, cookieFile, envFile], {
    cwd: webRoot,
    stdio: 'inherit',
  });
  devCookieCapture.on('exit', code => {
    devCookieCapture = undefined;
    if (code === 0) {
      captureCooldownUntil = Date.now() + 5_000;
      reloadLocalEnv(envFile);
      const nextCookie = readCookieFile();
      const nextCsrf = process.env.BKLOG_CSRF_TOKEN || csrfFromCookie(nextCookie) || liveCsrfToken;
      syncProxyHeaders(devServer, nextCookie, nextCsrf);
      devServer?.config.logger.info('[web-v3] 已热加载最新 Cookie 与 BKLOG_CSRF_TOKEN');
    } else {
      captureCooldownUntil = Date.now() + 30_000;
      console.warn('[web-v3] 浏览器授权未完成，30 秒内不再重复拉起');
    }
  });
}

function configureDevProxy(proxyServer: { on: (event: string, listener: (...args: any[]) => void) => void }) {
  proxyServer.on('proxyReq', (proxyReq: { setHeader: (name: string, value: string) => void }) => {
    if (liveCookie) proxyReq.setHeader('Cookie', liveCookie);
    if (liveCsrfToken) proxyReq.setHeader('X-CSRFToken', liveCsrfToken);
  });
  proxyServer.on('proxyRes', (proxyRes: { statusCode?: number; headers: Record<string, string | string[] | undefined> }) => {
    const location = proxyRes.headers.location;
    const target = Array.isArray(location) ? location[0] : location || '';
    if (isAuthExpiredResponse(proxyRes.statusCode || 0, target)) captureDevCookie();
  });
}

const proxy = Object.fromEntries(
  proxyContexts.map((context: string) => [
    context,
    {
      target: proxyTarget,
      changeOrigin: proxyRule.changeOrigin !== false,
      secure: proxyRule.secure === true,
      headers: { ...proxyHeaders },
      configure: configureDevProxy,
    },
  ]),
);
console.info(
  `[web-v3] /api 代理目标${proxyTarget ? '已配置' : '未配置'}，登录头${liveCookie ? '已从 .cookie 加载' : '缺失'}`,
);

function watchDevLocalFiles(): Plugin {
  return {
    name: 'bklog-dev-local-files',
    apply: 'serve',
    configureServer(server) {
      devServer = server;
      if (localFileWatchStarted) return;
      localFileWatchStarted = true;

      const watch = (file: string, onChange: () => void) => {
        watchFile(file, { interval: 300 }, (current, previous) => {
          if (current.mtimeMs === previous.mtimeMs && current.size === previous.size) return;
          onChange();
        });
      };

      watch(cookieFile, () => {
        if (!devServer) return;
        const cookie = readCookieFile();
        const csrf = csrfFromCookie(cookie) || process.env.BKLOG_CSRF_TOKEN || liveCsrfToken;
        syncProxyHeaders(devServer, cookie, csrf);
        devServer.config.logger.info(
          `[web-v3] .cookie 已更新，代理登录头${cookie ? '已热更新' : '已清空'}`,
        );
      });

      let envTimer: ReturnType<typeof setTimeout> | undefined;
      watch(envFile, () => {
        if (envTimer) clearTimeout(envTimer);
        envTimer = setTimeout(() => {
          const prevProxy = process.env.BKLOG_DEV_PROXY_URL;
          const prevHost = process.env.BKLOG_DEV_HOST;
          const prevAllowed = process.env.BKLOG_DEV_ALLOWED_HOSTS;
          const prevUrl = process.env.BKLOG_DEV_URL;
          reloadLocalEnv(envFile);
          const nextCsrf = process.env.BKLOG_CSRF_TOKEN || csrfFromCookie(liveCookie) || liveCsrfToken;
          syncProxyHeaders(devServer, liveCookie, nextCsrf);
          const needRestart =
            prevProxy !== process.env.BKLOG_DEV_PROXY_URL
            || prevHost !== process.env.BKLOG_DEV_HOST
            || prevAllowed !== process.env.BKLOG_DEV_ALLOWED_HOSTS
            || prevUrl !== process.env.BKLOG_DEV_URL;
          if (needRestart) {
            delete require.cache[settingsFile];
            devServer?.config.logger.info('[web-v3] .env.local 代理或主机配置已更新，正在热重启开发服务');
            devServer?.restart();
          } else {
            devServer?.config.logger.info('[web-v3] .env.local 中的 BKLOG_CSRF_TOKEN 已热更新');
          }
        }, 200);
      });
    },
  };
}

export default defineConfig({
  plugins: [vue(), watchDevLocalFiles()],
  server: {
    host: '0.0.0.0',
    port: 4173,
    allowedHosts: allowedHosts(),
    proxy,
  },
});
