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
const wepack = require('webpack');
const path = require('path');
const fs = require('fs');
const { transformAppDir, transformDistDir } = require('./webpack/utils');
const CopyPlugin = require('copy-webpack-plugin');
const MonitorWebpackPlugin = require('./webpack/monitor-webpack-plugin');

const devProxyUrl = 'http://appdev.bktencent.com:9002';
const devHost = 'appdev.bktencent.com';
const loginHost = 'https://paas-dev.bktencent.com';
const devPort = 7001;
let devConfig = {
  port: devPort,
  host: devHost,
  devProxyUrl,
  loginHost,
  proxy: {},
  cache: null
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
      stopPort: 8888
    });
    config.devServer = {
      port,
      host: devConfig.host,
      proxy: {
        ...devConfig.proxy,
        proxyTimeout: 5 * 60 * 1000,
        timeout: 5 * 60 * 1000
      },
      client: {
        overlay: false
      },
      open: false,
      static: [],
      watchFiles: []
    };
    config.plugins.push(
      new wepack.DefinePlugin({
        process: {
          env: {
            NODE_ENV: JSON.stringify('development'),
            proxyUrl: JSON.stringify(devConfig.devProxyUrl),
            devUrl: JSON.stringify(`${devConfig.host}:${port}`),
            devHost: JSON.stringify(`${devConfig.host}`),
            loginHost: JSON.stringify(devConfig.loginHost),
            loginUrl: JSON.stringify(`${devConfig.loginHost}`),
            defaultBizId: JSON.stringify(`${devConfig.defaultBizId || 2}`),
            APP: JSON.stringify(`${app}`)
          }
        }
      })
    );
  } else if (app !== 'email') {
    config.plugins.push(
      new wepack.DefinePlugin({
        process: {
          env: {
            NODE_ENV: JSON.stringify('production'),
            APP: JSON.stringify(`${app}`)
          }
        }
      })
    );
    // pulic
    config.plugins.push(
      new CopyPlugin({
        patterns: [
          { from: path.resolve(`./public/${app}/`), to: distUrl },
          { from: path.resolve('./public/img'), to: path.resolve(distUrl, './img') }
        ]
      })
    );
    config.plugins.push(new MonitorWebpackPlugin(app));
  }
  const appDirName = transformAppDir(app);
  const appDir = `./src/${appDirName}/`;
  return {
    ...config,
    output: {
      publicPath: '',
      ...config.output,
      path: distUrl,
      uniqueName: app
    },
    entry: {
      ...config.entry,
      main: `./src/${appDirName}/index.ts`
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
        ...(['apm', 'fta', 'pc'].includes(app)
          ? {
              vue$: 'vue/dist/vue.runtime.common.js'
            }
          : {})
      }
    }
  };
};
