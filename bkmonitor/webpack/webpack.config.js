const CopyPlugin = require('copy-webpack-plugin');
const fs = require('node:fs');
const path = require('node:path');
const webpack = require('webpack');

const { createTraceWebpackIfdefRules } = require('./scripts/monitor-alarm-center/trace-ifdef-webpack.js');
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

/** weweb 子应用跑在 7002、主应用在 7001，跨端口请求需要这些 CORS 头；尤其是 axios 注入的 traceparent */
const DEV_CORS_HEADERS = {
  'Access-Control-Allow-Origin': `http://${devConfig.host}:${devPort}`,
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
  'Access-Control-Allow-Headers':
    'traceparent, x-csrftoken, cookie, x-requested-with, source-app, authorization, content-type, accept, accept-encoding, accept-language, cache-control, pragma, origin, referer, user-agent, dnt',
  'Access-Control-Allow-Credentials': true,
};

const applyDevCorsHeaders = target => {
  for (const [key, value] of Object.entries(DEV_CORS_HEADERS)) {
    target[key.toLowerCase()] = value;
  }
};

/** OPTIONS 预检不能转发给后端：后端 Allow-Headers 不含 traceparent，浏览器会直接拦请求 */
const handleDevCorsPreflight = (req, res, next) => {
  if (req.method === 'OPTIONS') {
    for (const [key, value] of Object.entries(DEV_CORS_HEADERS)) {
      res.setHeader(key, value);
    }
    res.statusCode = 204;
    res.setHeader('Content-Length', '0');
    res.end();
    return;
  }
  next();
};

/** trace Worker 源码以字符串打入主 bundle，运行时通过 Blob URL 创建 Worker */
const setupTraceWorkerWebpack = config => {
  const workerRawRule = {
    resourceQuery: /raw/,
    type: 'asset/source',
  };
  const oneOfRule = config.module.rules.find(rule => rule.oneOf);
  if (oneOfRule) {
    oneOfRule.oneOf.unshift(workerRawRule);
    return;
  }
  config.module.rules.unshift(workerRawRule);
};

module.exports = async (baseConfig, { production, app }) => {
  const distUrl = path.resolve(`./${transformDistDir(app)}/`);
  const config = baseConfig;
  let activePort = devConfig.port;

  if (app === 'trace') {
    config.module.rules.unshift(...createTraceWebpackIfdefRules(__dirname, production));
    setupTraceWorkerWebpack(config);
  }
  if (!production) {
    // 自动配port
    activePort = await require('portfinder').getPortPromise({
      port: devConfig.port,
      stopPort: 8888,
    });
    config.devServer = {
      port: activePort,
      host: devConfig.host,
      allowedHosts: 'all',
      server: 'http',
      proxy: ['proxy', 'logProxy', 'tenantProxy'] // 监控平台、日志平台、租户平台代理配置
        .map(key => {
          const proxyItem = devConfig[key];
          if (!proxyItem?.target) return undefined;
          const prevOnProxyRes = proxyItem.onProxyRes;
          return {
            ...proxyItem,
            proxyTimeout: 5 * 60 * 1000,
            timeout: 5 * 60 * 1000,
            onProxyRes: (proxyRes, req, res) => {
              applyDevCorsHeaders(proxyRes.headers);
              prevOnProxyRes?.(proxyRes, req, res);
            },
          };
        })
        .filter(Boolean),
      client: {
        overlay: false,
      },
      headers: DEV_CORS_HEADERS,
      // 必须插在 http-proxy-middleware 之前，否则 OPTIONS 会被转发到测试环境
      setupMiddlewares: middlewares => {
        const proxyIndex = middlewares.findIndex(item => item.name === 'http-proxy-middleware');
        const corsMiddleware = { name: 'dev-cors-preflight', middleware: handleDevCorsPreflight };
        if (proxyIndex === -1) {
          middlewares.unshift(corsMiddleware);
        } else {
          middlewares.splice(proxyIndex, 0, corsMiddleware);
        }
        return middlewares;
      },
      open: false,
      static: [],
      watchFiles: [],
    };
    config.plugins.push(
      new webpack.DefinePlugin({
        ...(app === 'trace'
          ? {
              __VUE_OPTIONS_API__: 'true',
              __VUE_PROD_DEVTOOLS__: 'false',
              __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
            }
          : {
              __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
            }),
        process: {
          env: {
            NODE_ENV: JSON.stringify('development'),
            proxyUrl: JSON.stringify(devConfig.devProxyUrl),
            devUrl: JSON.stringify(`${devConfig.host}:${activePort}`),
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
      'vue-i18n': path.resolve(__dirname, `./src/${appDirName}/node_modules/vue-i18n/dist/vue-i18n.esm.js`),
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
        '@': path.resolve(__dirname, appDir),
        '@router': path.resolve(`./src/${appDirName}/router/`),
        '@store': path.resolve(`./src/${appDirName}/store/`),
        '@page': path.resolve(`./src/${appDirName}/pages/`),
        '@api': path.resolve('./src/monitor-api/'),
        '@static': path.resolve('./src/monitor-static/'),
        '@common': path.resolve('./src/monitor-common/'),
        // 'monitor-trace-explore': path.resolve(__dirname, './monitor-trace-explore/index.js'),
        // 'monitor-alarm-center': path.resolve(__dirname, './monitor-alarm-center/index.js'),
        ...vueAlias,
      },
    },
    devtool: production ? 'hidden-source-map' : 'source-map',
    cache: production ? false : config.cache,
  };
};
