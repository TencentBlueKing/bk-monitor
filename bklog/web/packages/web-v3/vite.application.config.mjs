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

import { datePickerIsland } from './tools/date-picker-island.ts';
import { paraglideVitePlugin } from '@inlang/paraglide-js';
import paraglideConfig from './project.inlang/paraglide.config.mjs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import vue from '@vitejs/plugin-vue';
import vueJsx from '@vitejs/plugin-vue-jsx';
import native from './vite.application-source.config';
import { monitorHostFixture } from './tools/monitor-host-fixture.mjs';
import { legacyStaticEntry } from './tools/legacy-static-entry.mjs';
import { legacyRefsVitePlugin, legacyRefsEsbuildPlugin } from './migration-runtime/legacy-refs.mjs';
import { nativeSdkVueVitePlugin, nativeSdkVueEsbuildPlugin } from './tools/native-sdk-vue.mjs';
const here = fileURLToPath(new URL('.', import.meta.url));
const require = createRequire(import.meta.url);
const plugins = native.plugins
  .flat(Infinity)
  .filter(plugin => plugin && !['vite:vue', 'vite:vue-jsx'].includes(plugin.name));
export default {
  ...native,
  publicDir: resolve(here, 'public'),
  cacheDir: resolve(here, 'node_modules/.vite-application'),
  optimizeDeps: {
    ...native.optimizeDeps,
    noDiscovery: false,
    entries: ['index.html'],
    esbuildOptions: {
      ...native.optimizeDeps.esbuildOptions,
      loader: { ...native.optimizeDeps.esbuildOptions.loader, '.js': 'jsx' },
      plugins: [...(native.optimizeDeps.esbuildOptions.plugins || []), legacyRefsEsbuildPlugin(), nativeSdkVueEsbuildPlugin(here)],
    },
  },
  plugins: [
    datePickerIsland(here),
    paraglideVitePlugin({ ...paraglideConfig, project: resolve(here, 'project.inlang'), outdir: resolve(here, '.paraglide') }),
    monitorHostFixture(here),
    legacyStaticEntry(),
    {
      name: 'application-source-boundary',
      generateBundle() {
        const forbidden = [...this.getModuleIds()].filter(id => id.startsWith(resolve(here, 'src-native') + '/'));
        if (forbidden.length) this.error('Application build imported the comparison baseline: ' + forbidden.join(', '));
      },
    },
    legacyRefsVitePlugin(),
    nativeSdkVueVitePlugin(here),
    ...plugins,
    {
      name: 'migration-json-response-diagnostics',
      apply: 'serve',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const path = new URL(req.url || '/', 'http://localhost').pathname;
          const expectsJson = `${req.headers['content-type'] || ''} ${req.headers.accept || ''}`.includes(
            'application/json',
          );
          res.once('finish', () => {
            if (expectsJson && String(res.getHeader('content-type') || '').includes('text/html')) {
              server.config.logger.warn(
                `[migration-json-response] ${req.method} ${path} returned HTML (${res.statusCode})`,
              );
            }
          });
          next();
        });
      },
    },
    vue({
      script: { babelParserPlugins: ['jsx', 'decorators-legacy'] },
      template: { compilerOptions: { compatConfig: { MODE: 2 }, isCustomElement: tag => tag === 'bk-user-display-name' } },
    }),
    vueJsx({
      // This SDK registers a browser Custom Element, not a Vue component.
      isCustomElement: tag => tag === 'bk-user-display-name',
      include: [/\.[jt]sx$/, /src\/.*\.jsx?$/, /\.vue\?vue&type=script.*lang\.[jt]sx$/],
      babelPlugins: [
        [require.resolve('@babel/plugin-proposal-decorators'), { legacy: true }],
        [require.resolve('@babel/plugin-transform-class-properties'), { loose: true }],
      ],
    }),
    {
      name: 'migration-test-label',
      transformIndexHtml(html) {
        return html.replace('日志平台 · 原生 Vue3 升级测试', '日志平台 · Vue3 UI 对齐');
      },
    },
    {
      name: 'migration-startup-diagnostics',
      apply: 'serve',
      transformIndexHtml: {
        order: 'pre',
        handler(html) {
          return html.replace(
            '<script type="module" src="/main.ts"></script>',
            `<script type="module">
      const report = error => {
        const panel = document.createElement('pre'); panel.setAttribute('role', 'alert');
        panel.style.cssText = 'white-space:pre-wrap;padding:20px;color:#b40000;background:#fff';
        panel.textContent = '源码升级启动错误\\n' + (error?.stack || error?.message || String(error));
        document.body.appendChild(panel); console.error(error);
      };
      window.addEventListener('error', event => { if(event.error) report(event.error); });
      window.addEventListener('unhandledrejection', event => report(event.reason));
      const fetchSource = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const response = await fetchSource(...args);
        const parseJson = response.json.bind(response);
        response.json = (...jsonArgs) => parseJson(...jsonArgs).catch(error => {
          console.error('[migration-json-response]', new URL(response.url).pathname, response.status, response.headers.get('content-type'));
          throw error;
        });
        return response;
      };
      console.info('[migration-test] loading src/main.ts');
      import('/main.ts').then(() => console.info('[migration-test] entry evaluated')).catch(report);
    </script>`,
          );
        },
      },
    },
  ],
  resolve: {
    ...native.resolve,
    alias: native.resolve.alias.map(item =>
      item.find.toString() === '/^vue$/' ? { ...item, replacement: resolve(here, 'src/platform/compat/vue-runtime.mjs') } : item,
    ),
  },
  server: { ...native.server, port: 4176, strictPort: true },
  build: { ...native.build, outDir: resolve(here, 'dist') },
};
