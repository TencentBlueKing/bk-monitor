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

const outputUrl = resolve(
  __dirname,
  `../monitor-${process.env.MONITOR_APP}-retrieve`,
);

const createMonitorConfig = (config) => {
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
            from: resolve(
              __dirname,
              '../node_modules/bk-magic-vue/dist/fonts/iconcool.*',
            ),
            to: resolve(outputUrl, './fonts/[name][ext]'),
          }
          : undefined,
        isTrace
          ? {
            from: resolve(
              __dirname,
              '../node_modules/bk-magic-vue/dist/images/*.(png|svg)',
            ),
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
  // 将 Worker 工厂替换为 Monitor 嵌入构建使用的 Blob 内联实现。
  // 默认工厂与各 worker 同目录；Monitor 变体位于
  // retrieve-v3/monitor/worker-factories/，仅在本构建中接入。
  config.plugins.push(
    new webpack.NormalModuleReplacementPlugin(
      /create-retrieve-search-worker(?:\.ts)?$/,
      (resource) => {
        if (resource.request.includes('worker-factories')) return;
        resource.request = resolve(
          __dirname,
          '../src/views/retrieve-v3/monitor/worker-factories/create-retrieve-search-worker.ts',
        );
      },
    ),
  );
  config.plugins.push(
    new webpack.NormalModuleReplacementPlugin(
      /create-trend-chart-worker(?:\.ts)?$/,
      (resource) => {
        if (resource.request.includes('worker-factories')) return;
        resource.request = resolve(
          __dirname,
          '../src/views/retrieve-v3/monitor/worker-factories/create-trend-chart-worker.ts',
        );
      },
    ),
  );
  config.plugins.push(new DropExternalWorkerAssetsPlugin());

  const fileLoaders = config.module.rules[1].oneOf.find((item) =>
    item.test.test('.ttf'),
  );
  const imgLoaders = config.module.rules[1].oneOf.find((item) =>
    item.test.test('.png'),
  );
  const urlLoaderOptions = fileLoaders.use.find(
    (item) => item.loader === 'url-loader',
  ).options;
  imgLoaders.options.publicPath = '../img';
  urlLoaderOptions.publicPath = '../fonts';

  return {
    ...config,
    entry: {
      main: isTrace
        ? './src/views/retrieve-v3/monitor/trace.ts'
        : './src/views/retrieve-v3/monitor/apm.ts',
    },
    output: {
      filename: '[name].js',
      path: outputUrl,
      library: {
        type: 'commonjs',
      },
      environment: {
        module: false,
      },
      chunkFormat: 'commonjs',
      module: false,
      clean: true,
      publicPath: '',
      // Worker 已 Blob 内联；对残留路径仍保留经典 worker 加载配置。
      workerChunkLoading: 'import-scripts',
    },
    resolveLoader: {
      ...config.resolveLoader,
      alias: {
        ...config.resolveLoader?.alias,
        // worker-loader 会把本构建的 commonjs externals 带进 Worker 子编译，
        // 内联 Worker 里出现 require() 就会运行期报错，故统一走包装 loader。
        'monitor-inline-worker-loader': resolve(
          __dirname,
          './inline-worker-loader.js',
        ),
      },
    },
    resolve: {
      ...config.resolve,
      alias: {
        ...config.resolve?.alias,
        vue$: 'vue/dist/vue.esm.js',
        '@': resolve('src'),
        // 强制 CodeMirror 运行时单例，避免跨包 instanceof 判断失效。
        '@codemirror/state$': resolve(__dirname, '../node_modules/@codemirror/state'),
        '@codemirror/view$': resolve(__dirname, '../node_modules/@codemirror/view'),
        codemirror$: resolve(__dirname, '../node_modules/codemirror/dist/index.js'),
      },
    },
    experiments: {
      outputModule: false,
    },
    optimization: {
      minimize: false,
      mangleExports: false,
      // 尽量将库与内联 Worker 打成单一 main 产物。
      splitChunks: false,
    },
    externalsType: 'commonjs',
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
        // /lodash/,
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
        // /@blueking\/user-selector/,
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
        // /lodash/,
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
      .filter((plugin) => !(plugin instanceof HtmlWebpackPlugin))
      .map((plugin) => {
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


/**
 * 产物生成后，清理多余的 worker chunk / 资源文件。
 * Monitor 嵌入构建通过 worker-loader 将 Worker 内联为 Blob，
 * 因此独立的 worker 脚本不应打进 npm 包。
 */
class DropExternalWorkerAssetsPlugin {
  apply(compiler) {
    compiler.hooks.thisCompilation.tap(
      'DropExternalWorkerAssetsPlugin',
      (compilation) => {
        compilation.hooks.processAssets.tap(
          {
            name: 'DropExternalWorkerAssetsPlugin',
            stage: webpack.Compilation.PROCESS_ASSETS_STAGE_OPTIMIZE_INLINE,
          },
          (assets) => {
            for (const name of Object.keys(assets)) {
              if (name === 'main.js' || name.startsWith('css/')) continue;
              // 保留 package 元信息以及 trace UI 复制过来的静态资源。
              if (name === 'package.json' || name.startsWith('fonts/') || name.startsWith('images/') || name.startsWith('img/')) {
                continue;
              }
              // 删除 webpack worker chunk（如 548.js）以及散落的 worker 资源（*.ts 哈希文件）。
              if (/^\d+\.js$/.test(name) || name.endsWith('.worker.js') || name.endsWith('.ts')) {
                compilation.deleteAsset(name);
              }
            }
          },
        );
      },
    );
  }
}

module.exports = {
  createMonitorConfig,
};
