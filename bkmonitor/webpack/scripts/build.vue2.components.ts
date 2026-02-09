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

import { getBabelOutputPlugin } from '@rollup/plugin-babel';
import vueTsx from '@vitejs/plugin-vue2-jsx';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import { analyzer } from 'vite-bundle-analyzer';
import { viteStaticCopy } from 'vite-plugin-static-copy';
const outputDir = resolve(__dirname, '../monitor-vue2-components');
export default defineConfig({
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV),
    'process.env.APP': JSON.stringify(''),
  },
  resolve: {
    alias: [
      {
        find: '@',
        replacement: resolve(__dirname, '../src/monitor-pc'),
      },
    ],
  },
  plugins: [
    vueTsx({
      babelPlugins: [
        ['@babel/plugin-proposal-decorators', { legacy: true }],
        ['@babel/plugin-proposal-class-properties', { loose: true }],
      ],
    }),
    viteStaticCopy({
      targets: [
        {
          src: resolve(__dirname, './package.vue2.json'),
          dest: outputDir,
          rename: 'package.json',
        },
        // {
        //   src: resolve(__dirname, '../src/trace/components/retrieval-filter/readme.md'),
        //   dest: outputDir,
        // },
      ],
    }),
    analyzer(),
  ],
  build: {
    copyPublicDir: false,
    emptyOutDir: true,
    outDir: outputDir,
    minify: false,
    lib: {
      entry: {
        index: resolve(__dirname, '../src/monitor-pc/components.ts'),
        'monitor-vue2': resolve(__dirname, '../src/trace/pages/trace-explore/monitor-vue2.tsx'),
      },
      name: 'monitor-vue2-components',
      fileName: (_format, entryName) => {
        return `${entryName}.mjs`;
      },
      formats: ['es'],
    },
    rollupOptions: {
      plugins: [
        getBabelOutputPlugin({
          presets: [
            [
              '@babel/preset-env',
              {
                targets: {
                  browsers: ['> 0.3%', 'Chrome > 90', 'last 2 versions', 'Firefox ESR', 'not dead'],
                  node: 'current',
                },
                useBuiltIns: 'usage',
                corejs: 3,
                debug: false,
              },
            ],
            [
              '@vue/babel-preset-jsx',
              {
                compositionAPI: 'native',
                functional: true,
                injectH: true,
                vModel: true,
                vOn: true,
              },
            ],
          ],
          plugins: ['@babel/plugin-transform-runtime'],
        }),
      ],
      output: {
        assetFileNames: 'index.css',
      },
      external: (source: string, importer: string | undefined) => {
        if (
          /^dayjs[/]?\w*/.test(source) ||
          /^@blueking\/monitor-vue2-components/.test(source) ||
          /@blueking\/bkui-library/.test(source)
        ) {
          return true;
        }
        if (/^vue$/.test(source)) {
          if (importer?.includes('monitor-vue2.tsx')) {
            return true;
          }
          return false;
        }
        return false;
      },
    },
  },
});
