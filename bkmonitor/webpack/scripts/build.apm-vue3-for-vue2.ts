/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

/**
 * `@blueking/apm-vue3-for-vue2` 的构建配置：APM 场景下给 **Vue2 宿主**用的 Vue3 mount* 挂载 API。
 *
 * 构建选项与 `@blueking/monitor-vue3-components` 完全共用，见 vue3-lib/create-config.ts。
 * 本包是 pnpm workspace（apm-vue3-for-vue2/package.json 提交在包根），产物只进 dist/。
 *
 * 模式跟 Vue2 宿主走（webpack/ensure-apm-vue3-for-vue2.js）：
 * - 宿主 dev：watch + development（也可单独 `pnpm dev:apm-vue3-for-vue2`）
 * - 宿主 build：一次性 production（也可单独 `pnpm build:apm-vue3-for-vue2`）
 * 都走 vue3-lib/vite-build.mjs，不要直接 vite CLI。
 */
import { resolve } from 'node:path';
import { defineConfig } from 'vite';

import { createVue3LibConfig } from './vue3-lib/create-config';

const packageDir = resolve(__dirname, '../apm-vue3-for-vue2');

export default defineConfig(({ mode }) => {
  const isDev = mode === 'development';
  const config = createVue3LibConfig({
    entry: resolve(__dirname, '../src/trace/apm-vue3-for-vue2.ts'),
    outputDir: resolve(packageDir, 'dist'),
    metaDir: packageDir,
    readmeFile: resolve(__dirname, '../src/trace/apm-vue3-for-vue2.md'),
  });
  return {
    ...config,
    define: {
      ...config.define,
      // Vite build 命令默认 NODE_ENV=production，watch 必须显式改成 development
      'process.env.NODE_ENV': JSON.stringify(isDev ? 'development' : 'production'),
    },
    build: {
      ...config.build,
      sourcemap: isDev,
      // watch 若清空 dist，宿主 webpack 会在空窗期解析不到 package exports 的 index.js / index.css
      emptyOutDir: !isDev,
    },
  };
});
