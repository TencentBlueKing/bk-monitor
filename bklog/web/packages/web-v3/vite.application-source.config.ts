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

import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, mergeConfig } from 'vite';
import vueJsx from '@vitejs/plugin-vue-jsx';
import base from './vite.base.config';
const here = dirname(fileURLToPath(import.meta.url));
const sourceRoot = resolve(here, 'src');
const require = createRequire(resolve(here, 'package.json'));
const { parse: preprocess } = require('ifdef-loader/preprocessor');
const app = process.env.MONITOR_APP || 'log';
const nativeConfig = mergeConfig(base, defineConfig({
 root: sourceRoot,
 cacheDir: resolve(here, 'node_modules/.vite-application-source'),
 publicDir: false,
 esbuild: { tsconfigRaw: { compilerOptions: { experimentalDecorators: true, useDefineForClassFields: false } } },
 plugins: [{
   name: 'native-source-conditional-build', enforce: 'pre',
   transform(code, id) {
     if (!id.startsWith(sourceRoot) || !/\.(?:[jt]sx?|vue)(?:\?|$)/.test(id)) return;
     if (!/#(?:if|else|endif|code)/.test(code)) return;
     return { code: preprocess(code, { MONITOR_APP: app }), map: null };
   },
 }, vueJsx()],
 resolve: { extensions: ['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json', '.vue'], alias: [
   { find: /^bkui-vue\/lib\/icon$/, replacement: resolve(sourceRoot, 'platform/compat/tdesign/bkui-icons.ts') },
   { find: /^bkui-vue\/lib\/form$/, replacement: resolve(sourceRoot, 'platform/compat/tdesign/bkui-vue.ts') },
   { find: /^bkui-vue$/, replacement: resolve(sourceRoot, 'platform/compat/tdesign/bkui-vue.ts') },
   { find: '@', replacement: sourceRoot },
   { find: /^path$/, replacement: require.resolve('path-browserify') },
   { find: /^vue$/, replacement: resolve(here, 'node_modules/vue/dist/vue.runtime.esm-bundler.js') },
   { find: /^vue-router$/, replacement: resolve(here, 'node_modules/vue-router/dist/vue-router.mjs') },
 ] },
 define: {
   'process.env.APP': JSON.stringify(app),
   'process.env.MONITOR_APP': JSON.stringify(app),
   'process.env.devHost': JSON.stringify('appdev.woa.com'),
   'process.env.devUrl': JSON.stringify('appdev.woa.com:4175'),
   'process.env.devProxyUrl': JSON.stringify(''),
 },
 optimizeDeps: { noDiscovery: true, include: ['vue', 'vue-router', 'pinia'], esbuildOptions: { loader: { '.eot': 'dataurl', '.woff': 'dataurl', '.woff2': 'dataurl', '.ttf': 'dataurl', '.svg': 'dataurl' } } },
 server: { port: 4176, strictPort: true },
 build: { outDir: resolve(here, 'dist'), emptyOutDir: true },
}));

// Source modules live under /api/*.js; they must not be sent to the backend proxy.
const apiProxy = nativeConfig.server?.proxy?.['/api'];
if (apiProxy && nativeConfig.server) {
  nativeConfig.server.proxy = {
    '^/api/(?![^?]*\\.(?:[cm]?[jt]sx?)(?:\\?|$))': apiProxy,
    '/notice/': apiProxy,
  };
}
export default nativeConfig;
