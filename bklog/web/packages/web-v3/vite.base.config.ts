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
loadLocalEnv(resolve(webRoot, '.env.local'));

function loadLocalSettings() {
  const cookieFile = resolve(webRoot, '.cookie');
  if (!existsSync(settingsFile)) {
    console.warn('[web-v3] 未找到 packages/web-v2/local.settings.js，/api 不会带登录头。');
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

const localSettings = loadLocalSettings();
const proxyRule = localSettings.proxy?.[0] ?? {};
const proxyTarget = proxyRule.target || localSettings.devProxyUrl || devProxyUrl();
const proxyHeaders = proxyRule.headers;
const proxyContexts = Array.isArray(proxyRule.context) && proxyRule.context.length ? proxyRule.context : ['/api'];
const proxy = Object.fromEntries(
  proxyContexts.map((context: string) => [
    context,
    {
      target: proxyTarget,
      changeOrigin: proxyRule.changeOrigin !== false,
      secure: proxyRule.secure === true,
      headers: proxyHeaders,
    },
  ]),
);
console.info(`[web-v3] /api 代理目标${proxyTarget ? '已配置' : '未配置'}，登录头${proxyHeaders?.Cookie ? '已从 .cookie 加载' : '缺失'}`);

const envFile = resolve(webRoot, '.env.local');
const cookieFile = resolve(webRoot, '.cookie');
let devServer: ViteDevServer | undefined;
let localFileWatchStarted = false;

function readCookieFile() {
  if (!existsSync(cookieFile)) return '';
  return readFileSync(cookieFile, 'utf8').trim();
}

function applyProxyCookie(server: ViteDevServer, cookie: string) {
  const rules = server.config.server.proxy;
  if (!rules) return;
  for (const rule of Object.values(rules)) {
    if (!rule || typeof rule === 'string') continue;
    const headers = (rule as ProxyOptions).headers;
    if (headers) headers.Cookie = cookie;
  }
}

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
        applyProxyCookie(devServer, cookie);
        devServer.config.logger.info(
          `[web-v3] .cookie 已更新，代理登录头${cookie ? '已热更新' : '已清空'}`,
        );
      });

      let envTimer: ReturnType<typeof setTimeout> | undefined;
      watch(envFile, () => {
        if (envTimer) clearTimeout(envTimer);
        envTimer = setTimeout(() => {
          reloadLocalEnv(envFile);
          delete require.cache[settingsFile];
          devServer?.config.logger.info('[web-v3] .env.local 已更新，正在热重启开发服务');
          devServer?.restart();
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
