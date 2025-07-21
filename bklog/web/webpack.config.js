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
const path = require('path');
const fs = require('fs');
const MonacoWebpackPlugin = require('monaco-editor-webpack-plugin');
const LogWebpackPlugin = require('./webpack/log-webpack-plugin');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const CliMonacoWebpackPlugin = require('monaco-editor-webpack-plugin');
const { createMonitorConfig } = require('./scripts/create-monitor');
const devProxyUrl = 'http://appdev.bktencent.com:9002';
const loginHost = 'https://paas-dev.bktencent.com';
const devPort = 8001;

let devConfig = {
  cache: null,
  devProxyUrl,
  loginHost,
  port: devPort,
  proxy: {},
};
const logPluginConfig = {
  pcBuildVariates: `
    <script>
      window.SITE_URL = '\${SITE_URL}'
      window.AJAX_URL_PREFIX = '\${AJAX_URL_PREFIX}'
      window.BK_STATIC_URL = '\${BK_STATIC_URL}'
      window.LOGIN_SERVICE_URL = '\${LOGIN_SERVICE_URL}'
      window.MONITOR_URL = '\${MONITOR_URL}'
      window.BKDATA_URL = '\${BKDATA_URL}'
      window.COLLECTOR_GUIDE_URL = '\${COLLECTOR_GUIDE_URL}'
      window.FEATURE_TOGGLE = \${FEATURE_TOGGLE | n}
      window.FEATURE_TOGGLE_WHITE_LIST = \${FEATURE_TOGGLE_WHITE_LIST | n}
      window.SPACE_UID_WHITE_LIST = \${SPACE_UID_WHITE_LIST | n}
      window.FIELD_ANALYSIS_CONFIG = \${FIELD_ANALYSIS_CONFIG | n}
      window.REAL_TIME_LOG_MAX_LENGTH = '\${REAL_TIME_LOG_MAX_LENGTH}'
      window.REAL_TIME_LOG_SHIFT_LENGTH = '\${REAL_TIME_LOG_SHIFT_LENGTH}'
      window.RUN_VER = '\${RUN_VER}'
      window.TITLE_MENU = '\${TITLE_MENU}'
      window.MENU_LOGO_URL = '\${MENU_LOGO_URL}'
      window.APP_CODE = '\${APP_CODE}'
      window.BK_DOC_URL = '\${BK_DOC_URL}'
      window.BK_FAQ_URL = '\${BK_FAQ_URL}'
      window.BK_DOC_QUERY_URL = '\${BK_DOC_QUERY_URL}'
      window.BK_HOT_WARM_CONFIG_URL = '\${BK_HOT_WARM_CONFIG_URL}'
      window.BIZ_ACCESS_URL = '\${BIZ_ACCESS_URL}'
      window.DEMO_BIZ_ID = \${DEMO_BIZ_ID}
      window.ES_STORAGE_CAPACITY = '\${ES_STORAGE_CAPACITY}'
      window.TAM_AEGIS_KEY = '\${TAM_AEGIS_KEY}'
      window.BK_LOGIN_URL = '\${BK_LOGIN_URL}'
      window.BK_DOC_DATA_URL = '\${BK_DOC_DATA_URL}'
      window.BK_PLAT_HOST = '\${BK_PLAT_HOST}'
      window.BK_ARCHIVE_DOC_URL = '\${BK_ARCHIVE_DOC_URL}'
      window.BK_ETL_DOC_URL = '\${BK_ETL_DOC_URL}'
      window.ASSESSMEN_HOST_COUNT = \${BK_ASSESSMEN_HOST_COUNT}
      window.ENABLE_CHECK_COLLECTOR = \${ENABLE_CHECK_COLLECTOR}
      window.IS_EXTERNAL = \${IS_EXTERNAL}
      window.BCS_WEB_CONSOLE_DOMAIN = '\${BCS_WEB_CONSOLE_DOMAIN}'
      window.VERSION = '\${VERSION}'
      window.BK_SHARED_RES_URL = '\${BK_SHARED_RES_URL}'
    </script>`,
};
if (fs.existsSync(path.resolve(__dirname, './local.settings.js'))) {
  const localConfig = require('./local.settings');
  devConfig = Object.assign({}, devConfig, localConfig);
}
module.exports = (baseConfig, { app, email = false, fta, log, mobile, production }) => {
  const isMonitorRetrieveBuild = ['apm', 'trace'].includes(process.env.MONITOR_APP) && production; // 判断是否监控检索构建
  const config = baseConfig;
  const distUrl = path.resolve('../static/dist');
  if (!production) {
    config.devServer = Object.assign({}, config.devServer || {}, {
      host: devConfig.host,
      open: false,
      port: devConfig.port,
      proxy: [
        {
          ...devConfig.proxy,
        },
      ],
      static: [],
    });
    config.plugins.push(
      new webpack.DefinePlugin({
        process: {
          env: {
            APP: JSON.stringify(`${process.env.MONITOR_APP}`),
            MONITOR_APP: JSON.stringify(`${process.env.MONITOR_APP}`),
            devHost: JSON.stringify(`${devConfig.host}`),
            devUrl: JSON.stringify(`${devConfig.host}:${devConfig.port}`),
            loginHost: JSON.stringify(devConfig.loginHost),
            loginUrl: JSON.stringify(`${devConfig.loginHost}/login/`),
            proxyUrl: JSON.stringify(devConfig.devProxyUrl),
          },
        },
      }),
    );
  } else if (!email && !isMonitorRetrieveBuild) {
    config.plugins.push(new LogWebpackPlugin({ ...logPluginConfig, fta, mobile }));
    config.plugins.push(
      new CopyWebpackPlugin({
        patterns: [
          {
            from: path.resolve(__dirname, './src/images/new-logo.svg'),
            to: path.resolve(distUrl, './img'),
          },
        ],
      }),
    );
    config.plugins.push(
      new webpack.DefinePlugin({
        process: {
          env: {
            APP: JSON.stringify(`${app}`),
            NODE_ENV: JSON.stringify('production'),
          },
        },
      }),
    );
  }
  // 监控检索构建
  if (isMonitorRetrieveBuild) {
    return createMonitorConfig(config);
  }
  config.plugins.forEach((item, index) => {
    if (item instanceof CliMonacoWebpackPlugin) {
      item.options.languages.push('yaml');
      item.options.languages.push('json');
      item.options.customLanguages = [
        {
          entry: 'monaco-yaml',
          label: 'yaml',
          worker: {
            entry: 'monaco-yaml/yaml.worker',
            id: 'monaco-yaml/yamlWorker',
          },
        },
      ];
      config.plugins[index] = new MonacoWebpackPlugin(item.options);
    }
  });
  return {
    ...config,
    cache: production
      ? false
      : {
          buildDependencies: {
            config: [__filename],
          },
          cacheDirectory: path.resolve(__dirname, '.cache'),
          name: `${process.env.MONITOR_APP || config.app}-cache`,
          type: 'filesystem',
        },
    entry: {
      ...config.entry,
      main: './src/main.js',
    },
    output: {
      ...config.output,
      path: distUrl,
    },
    plugins: baseConfig.plugins.map(plugin => {
      return plugin instanceof webpack.ProgressPlugin
        ? new WebpackBar({
            name: `日志平台 ${production ? 'Production模式' : 'Development模式'} 构建`,
            profile: true,
          })
        : plugin;
    }),
    resolve: {
      ...config.resolve,
      alias: {
        '@': path.resolve('src'),
        vue$: 'vue/dist/vue.esm.js',
      },
    },
  };
};
