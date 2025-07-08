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
const webpack = require('webpack');
const WebpackBar = require('webpackbar');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const { resolve } = require('node:path');
const outputUrl = resolve(__dirname, `../monitor-${process.env.MONITOR_APP}-retrieve`);
const createMonitorConfig = config => {
  const production = process.env.NODE_ENV === 'production';
  const isTrace = process.env.MONITOR_APP === 'trace';
  config.plugins.push(
    new CopyWebpackPlugin({
      patterns: [
        {
          from: resolve(__dirname, `./${process.env.MONITOR_APP}-package.json`),
          to: resolve(outputUrl, './package.json'),
        },
        isTrace
          ? {
              from: resolve(__dirname, '../node_modules/bk-magic-vue/dist/fonts/iconcool.*'),
              to: resolve(outputUrl, './fonts/[name][ext]'),
            }
          : undefined,
        isTrace
          ? {
              from: resolve(__dirname, '../node_modules/bk-magic-vue/dist/images/*.(png|svg)'),
              to: resolve(outputUrl, './images/[name][ext]'),
            }
          : undefined,
      ].filter(Boolean),
    }),
  );
  config.plugins.push(
    new webpack.DefinePlugin({
      NODE_ENV: JSON.stringify('production'),
      APP: JSON.stringify(process.env.MONITOR_APP),
      MONITOR_APP: JSON.stringify(process.env.MONITOR_APP),
    }),
  );
  const fileLoaders = config.module.rules[1].oneOf.find(item => item.test.test('.ttf'));
  const imgLoaders = config.module.rules[1].oneOf.find(item => item.test.test('.png'));
  const urlLoaderOptions = fileLoaders.use.find(item => item.loader === 'url-loader').options;
  imgLoaders.options.publicPath = '../img';
  urlLoaderOptions.publicPath = '../fonts';
  return {
    ...config,
    entry: {
      main: isTrace ? './src/views/retrieve-v3/monitor/trace.ts' : './src/views/retrieve-v3/monitor/apm.ts',
    },
    output: {
      filename: '[name].js',
      path: outputUrl,
      library: {
        type: 'module',
      },
      environment: {
        module: true,
      },
      chunkFormat: 'module',
      module: true,
      clean: true,
      publicPath: '',
    },
    resolve: {
      ...config.resolve,
      alias: {
        vue$: 'vue/dist/vue.esm.js',
        '@': resolve('src'),
      },
    },
    experiments: {
      outputModule: true,
    },
    optimization: {
      minimize: false,
      mangleExports: false,
    },
    externalsType: 'module',
    externals: isTrace
      ? [
          /@blueking\/date-picker/,
          // /@blueking\/ip-selector/,
          // /@blueking\/user-selector/,
          /@blueking\/bkui-library/,
          // /@blueking\/ai-blueking/,
          // /bk-magic-vue/,
          // /vue-i18n/,
          // 'vue',
          'axios',
          // 'vuex',
          // 'vue-property-decorator',
          'vuedraggable',
          'sortablejs',
          // 'clipboard',
          // 'vue-tsx-support',
          'qs',
          /dayjs\//,
          'dayjs',
          // /echarts\/*/,
          /lodash/,
          // /vue-json-pretty/,
          ({ request }, cb) => {
            if (request === 'echarts') {
              return cb(undefined, request.replace(request, request));
            }
            if (request === 'resize-detector') {
              return cb(undefined, '@blueking/fork-resize-detector');
            }
            cb();
          },
        ]
      : [
          /@blueking\/date-picker/,
          // /@blueking\/ai-blueking/,
          /@blueking\/ip-selector/,
          /@blueking\/user-selector/,
          /@blueking\/bkui-library/,
          /bk-magic-vue/,
          /vue-i18n/,
          'vue',
          'axios',
          'vuex',
          'vue-property-decorator',
          'vuedraggable',
          'sortablejs',
          'clipboard',
          'vue-tsx-support',
          'qs',
          /dayjs\//,
          'dayjs',
          /lodash/,
          /vue-json-pretty/,
          /monaco-editor/,
          ({ request }, cb) => {
            if (request === 'echarts') {
              return cb(undefined, request.replace(request, request));
            }
            if (request === 'resize-detector') {
              return cb(undefined, '@blueking/fork-resize-detector');
            }
            cb();
          },
        ],
    plugins: config.plugins
      .filter(plugin => !(plugin instanceof HtmlWebpackPlugin))
      .map(plugin => {
        if (plugin instanceof MiniCssExtractPlugin) {
          return new MiniCssExtractPlugin({
            filename: 'css/main.css',
            ignoreOrder: true,
          });
        }
        return plugin instanceof webpack.ProgressPlugin
          ? new WebpackBar({
              profile: true,
              name: `监控日志检索组件 ${production ? 'Production模式' : 'Development模式'} 构建`,
            })
          : plugin;
      }),
    cache: production ? false : config.cache,
  };
};

module.exports = {
  createMonitorConfig,
};
