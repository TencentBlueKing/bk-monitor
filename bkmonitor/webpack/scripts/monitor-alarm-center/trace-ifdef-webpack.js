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

/* eslint-disable @typescript-eslint/no-require-imports -- CommonJS bridge loaded by webpack.config.js */

/**
 * Trace 主站 webpack 用的 ifdef 规则与选项（与 build.ts 中 Vite ifdefPlugin 对齐：
 * 独立 trace 为 IS_APM_MONITOR: false；告警中心 lib 构建为 true）。
 * 供项目根目录 webpack.config.js require；并由 build.ts 再导出，便于同目录单一入口。
 */
const path = require('node:path');

/**
 * `src/trace` 下 TS/TSX 与 SCSS 的 ifdef（`enforce: 'pre'`，须在 sass 等预处理之前）。
 * - TS/TSX：`ifdef-loader` + jsx-ifdef-normalize-loader（与 Vite 一致）。
 * - SCSS：仅 `ifdef-loader`（`// #if` 若交给 Sass 会先被当注释删掉）。
 *
 * @param {string} webpackRootDir 含 webpack.config.js 的工程根（一般为 __dirname）
 * @param {boolean} production
 * @returns {[import('webpack').RuleSetRule, import('webpack').RuleSetRule]}
 */
function createTraceWebpackIfdefRules(webpackRootDir, production) {
  const include = [path.resolve(webpackRootDir, 'src/trace')];
  const ifdefLoader = {
    loader: 'ifdef-loader',
    options: getTraceIfdefLoaderOptions(production),
  };
  return [
    {
      test: /\.tsx?$/,
      include,
      enforce: 'pre',
      resolve: {
        fullySpecified: false,
      },
      use: [ifdefLoader, path.resolve(webpackRootDir, 'webpack/jsx-ifdef-normalize-loader.js')],
    },
    {
      test: /\.scss$/,
      include,
      enforce: 'pre',
      use: [ifdefLoader],
    },
  ];
}

/** @param {boolean} production */
function getTraceIfdefLoaderOptions(production) {
  return {
    IS_APM_MONITOR: false,
    'ifdef-fill-with-blanks': true,
    'ifdef-triple-slash': false,
    'ifdef-uncomment-prefix': '// #code ',
    'ifdef-verbose': !production,
  };
}

module.exports = { createTraceWebpackIfdefRules };
