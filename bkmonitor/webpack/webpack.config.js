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
const CopyPlugin = require('copy-webpack-plugin');
const fs = require('node:fs');
const path = require('node:path');
const webpack = require('webpack');

const MonitorWebpackPlugin = require('./webpack/monitor-webpack-plugin');
const { transformAppDir, transformDistDir } = require('./webpack/utils');

const devProxyUrl = 'http://appdev.bktencent.com:9002';
const devHost = 'appdev.bktencent.com';
const devPort = 7001;
let devConfig = {
  port: devPort,
  host: devHost,
  devProxyUrl,
  proxy: {},
  logProxy: {},
};
if (fs.existsSync(path.resolve(__dirname, './local.settings.js'))) {
  const localConfig = require('./local.settings');
  devConfig = Object.assign({}, devConfig, localConfig);
}
module.exports = async (baseConfig, { production, app }) => {
  const distUrl = path.resolve(`./${transformDistDir(app)}/`);
  const config = baseConfig;
  if (!production) {
    // 自动配port
    const port = await require('portfinder').getPortPromise({
      port: devConfig.port,
      stopPort: 8888,
    });
    config.devServer = {
      port,
      host: devConfig.host,
      allowedHosts: 'all',
      proxy: [
        {
          ...devConfig.proxy,
          proxyTimeout: 5 * 60 * 1000,
          timeout: 5 * 60 * 1000,
        },
        {
          ...devConfig.logProxy,
          proxyTimeout: 5 * 60 * 1000,
          timeout: 5 * 60 * 1000,
        },
      ],
      client: {
        overlay: false,
      },
      headers: {
        'Access-Control-Allow-Origin': '*',
      },
      open: false,
      static: [],
      watchFiles: [],
    };
    config.plugins.push(
      new webpack.DefinePlugin({
        process: {
          env: {
            NODE_ENV: JSON.stringify('development'),
            proxyUrl: JSON.stringify(devConfig.devProxyUrl),
            devUrl: JSON.stringify(`${devConfig.host}:${port}`),
            devHost: JSON.stringify(`${devConfig.host}`),
            defaultBizId: JSON.stringify(`${devConfig.defaultBizId || 2}`),
            APP: JSON.stringify(`${app}`),
          },
        },
      })
    );
  } else if (app !== 'email') {
    config.plugins.push(
      new webpack.DefinePlugin({
        process: {
          env: {
            NODE_ENV: JSON.stringify('production'),
            APP: JSON.stringify(`${app}`),
          },
        },
      })
    );
    config.plugins.push(new MonitorWebpackPlugin(app));
  }
  const appDirName = transformAppDir(app);
  const appDir = `./src/${appDirName}/`;
  config.plugins.push(
    new CopyPlugin({
      patterns: [
        { from: path.resolve(`./public/${app}/`), to: distUrl },
        { from: path.resolve('./public/img'), to: path.resolve(distUrl, './img') },
      ].filter(Boolean),
    })
  );
  // 固定vue版本 分离vue3 和 vue2项目vue相关依赖
  let vueAlias = {};
  if (['apm', 'fta', 'pc', 'mobile'].includes(app)) {
    vueAlias = {
      vue$: path.resolve(`./src/${appDirName}/node_modules/vue/dist/vue.runtime.common.js`),
    };
  } else if (app === 'trace') {
    vueAlias = {
      vue$: path.resolve(__dirname, `./src/${appDirName}/node_modules/vue/dist/vue.runtime.esm-bundler.js`),
    };
  }
  return {
    ...config,
    output: {
      publicPath: '',
      ...config.output,
      path: distUrl,
      uniqueName: app,
      clean: true,
    },
    entry: {
      ...config.entry,
      main: `./src/${appDirName}/index.ts`,
    },
    resolve: {
      ...config.resolve,
      alias: {
        ...config.resolve.alias,
        '@': appDir,
        '@router': path.resolve(`./src/${appDirName}/router/`),
        '@store': path.resolve(`./src/${appDirName}/store/`),
        '@page': path.resolve(`./src/${appDirName}/pages/`),
        '@api': path.resolve('./src/monitor-api/'),
        '@static': path.resolve('./src/monitor-static/'),
        '@common': path.resolve('./src/monitor-common/'),
        ...vueAlias,
      },
    },
    devtool: 'source-map',
    cache: production ? false : config.cache,
  };
};
