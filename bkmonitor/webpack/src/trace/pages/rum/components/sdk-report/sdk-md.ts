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
export const OT_MD = `# @blueking/open-telemetry

\`@blueking/open-telemetry\` 是蓝鲸 RUM Web 上报 SDK。它基于 OpenTelemetry 采集页面访问、接口请求、静态资源、JS 错误、Web Vitals、白屏、设备、会话等数据，并通过 OTLP HTTP 上报到 collector。

## 1. 安装和使用

### npm 使用

\`\`\`bash
npm install @blueking/open-telemetry
\`\`\`

\`\`\`javascript
import { BkOpenTelemetry } from '@blueking/open-telemetry';

const bkOT = new BkOpenTelemetry({
  app: {
    name: 'demo-app',
    environment: 'production',
    version: '1.0.0',
  },
  transport: {
    endpoint: 'https://bk-rum.tencent.com/',
    token: 'your-report-token',
  },
  user: {
    id: window.USER_ID,
  },
});
\`\`\`

### CDN 使用

\`\`\`html
<script src="https://unpkg.com/@blueking/open-telemetry/dist/bk-rum.global.js"></script>
<script>
  window.bkOT = new window.BkOpenTelemetry({
    app: {
      name: 'demo-app',
      environment: 'production',
      version: '1.0.0',
    },
    transport: {
      endpoint: 'https://bk-rum.tencent.com/',
      token: 'your-report-token',
    },
    user: {
      id: window.USER_ID,
    },
  });
</script>
\`\`\`

\`new BkOpenTelemetry()\` 后默认自动启动，不需要再手动调用 \`start()\`。

\`transport.endpoint\` 填 OTLP collector 根地址即可，SDK 会自动拼出三类上报地址：

- traces: \`endpoint/v1/traces\`
- metrics: \`endpoint/v1/metrics\`
- logs: \`endpoint/v1/logs\`

\`transport.token\` 会作为默认鉴权头发送：\`Authorization: Bearer <token>\`。

## 2. 默认采集

只配置 \`app\` 和 \`transport\` 后，SDK 已经默认开启常用能力：

- \`documentLoad\`: 页面加载链路。
- \`pageView\`: 页面访问和 SPA 路由切换。
- \`fetch\`: 自动采集 fetch 接口请求。
- \`xhr\`: 自动采集 XMLHttpRequest 接口请求。
- \`resource\`: 静态资源加载耗时。
- \`error\`: JS 错误、Promise 异常、资源加载失败。
- \`webVitals\`: CLS、FCP、INP、LCP、TTFB。
- \`blankScreen\`: 首屏白屏检测。
- \`device\`: 设备、浏览器、屏幕、网络信息。
- \`session\`: 连续访问会话。
- \`userInteraction\`: OpenTelemetry 官方用户交互 instrumentation。

默认关闭的能力需要手动打开：

- \`action\`: 轻量用户操作事件，支持点击、输入、提交等。
- \`httpBody\`: 接口异常时采集请求和响应 body。
- \`longTask\`: 主线程 Long Task。
- \`routeTiming\`: SPA 路由切换耗时。
- \`cspViolation\`: CSP 违规事件。
- \`websocket\`: WebSocket 连接、消息、错误指标。

如果要关闭默认能力，显式配置为 \`false\`：

\`\`\`javascript
new BkOpenTelemetry({
  transport: {
    endpoint: 'https://bk-rum.tencent.com/',
  },
  instrumentations: {
    fetch: false,
    xhr: false,
    userInteraction: false,
  },
  plugins: {
    webVitals: false,
    blankScreen: false,
    session: false,
  },
});
\`\`\`

## 3. 给数据加上应用、用户和路由

建议先补齐应用标识、用户 ID 和路由归类。这样后续排查问题时，可以按应用、版本、用户、页面聚合。

\`\`\`javascript
const bkOT = new BkOpenTelemetry({
  app: {
    name: 'order-center',
    environment: 'production',
    version: '1.2.0',
  },
  transport: {
    endpoint: 'https://bk-rum.tencent.com/',
    token: 'your-report-token',
  },
  user: {
    id: window.USER_ID,
  },
  route: {
    getPathGroup: url => {
      const { pathname } = new URL(url, location.href);
      return pathname.replace(//user/d+/, '/user/:id');
    },
  },
});
\`\`\`

常用基础配置：

- \`app.name\`: 应用名，会写入 \`service.name\`，默认 \`unknown_service\`。
- \`app.environment\`: 环境名，会写入 \`deployment.environment.name\`，默认 \`production\`。
- \`app.version\`: 应用版本，会写入 \`service.version\`。
- \`user.id\`: 用户 ID，会写入 \`user.id\`。SDK 原样透传，不做 hash 和脱敏。
- \`route.getPathGroup\`: 把高基数 URL 归类成低基数路由，例如 \`/user/123\` 归类成 \`/user/:id\`。

运行中也可以更新用户和当前 View：

\`\`\`javascript
bkOT.setUser({ id: 'user-001' });

bkOT.setView({
  id: 'view-001',
  url: location.href,
  urlPathGroup: '/order/:id',
  loadingType: 'route_change',
});
\`\`\`

\`setUser\` 和 \`setView\` 会更新运行期公共属性，后续 span、metric、log 都会自动带上这些字段。

## 4. 按需打开接口、资源和路由能力

多数 Web 应用可以从这一组配置开始：

\`\`\`javascript
new BkOpenTelemetry({
  app: {
    name: 'demo-app',
    version: '1.0.0',
  },
  transport: {
    endpoint: 'https://your-otlp-collector',
    token: 'your-report-token',
  },
  route: {
    getPathGroup: url => new URL(url, location.href).pathname,
  },
  plugins: {
    routeTiming: true,
    longTask: { threshold: 80 },
  },
});
\`\`\`

- \`fetch\` / \`xhr\`: 默认开启，采集接口耗时、状态码、请求方法、URL 归类等。
- \`resource\`: 默认开启，采集 img、script、css 等静态资源耗时、大小、缓存命中和协议。
- \`pageView\`: 默认开启，监听 \`pushState\`、\`replaceState\`、\`popstate\`、\`hashchange\`。
- \`routeTiming\`: 默认关闭，估算 SPA 路由切换到下一帧渲染完成的耗时。
- \`longTask\`: 默认关闭，采集主线程长任务。\`threshold\` 默认 \`50\` ms。

SDK 会自动忽略指向自身 OTLP 上报地址的请求，避免上报请求被再次采集导致循环放大。

## 5. 配置错误、白屏和 CSP

\`\`\`javascript
new BkOpenTelemetry({
  transport: {
    endpoint: 'https://bk-rum.tencent.com/',
  },
  plugins: {
    error: {
      windowMs: 60 * 1000,
      maxPerWindow: 5,
    },
    blankScreen: {
      rootSelector: '#app',
      checkDelay: 3000,
      threshold: 0.8,
      ignoreSelectors: ['.app-loading', '.page-skeleton'],
    },
    cspViolation: true,
  },
});
\`\`\`

错误采集说明：

- \`error\`: 默认开启，采集 \`window.error\`、\`unhandledrejection\`、资源加载失败。
- \`error.windowMs\`: 同类错误节流窗口，默认 \`60000\` ms。
- \`error.maxPerWindow\`: 同类错误在窗口内最多上报条数，默认 \`5\`。
- \`cspViolation\`: 默认关闭，监听 \`securitypolicyviolation\` 事件。适合有 CSP 策略的站点开启。

白屏检测说明：

- \`blankScreen\`: 默认开启，只在判定为白屏时上报。
- \`blankScreen.rootSelector\`: 应用挂载点。Vue / React 项目建议配置为 \`#app\` 或 \`#root\`。
- \`blankScreen.checkDelay\`: DOM ready 后延迟多久检测，默认 \`3000\` ms。
- \`blankScreen.threshold\`: 空白采样点比例阈值，范围 \`0 - 1\`，默认 \`0.8\`。
- \`blankScreen.ignoreSelectors\`: 追加 loading、骨架屏等忽略选择器，命中后不计入空白比例。

## 6. 配置用户操作和 WebSocket

\`\`\`javascript
new BkOpenTelemetry({
  transport: {
    endpoint: 'https://bk-rum.tencent.com/',
  },
  plugins: {
    action: {
      eventNames: ['click', 'submit', 'keydown'],
    },
    websocket: true,
  },
});
\`\`\`

\`action\` 用于上报轻量用户操作：

- \`action: true\`: 采集 \`click\`、\`submit\`、\`keydown\`。
- \`action.eventNames\`: 自定义采集事件，支持 \`click\`、\`input\`、\`keydown\`、\`pointerdown\`、\`scroll\`、\`submit\`。
- 上报时会截取元素文本、标签名，并写入 \`action.type\`、\`target.text_short\`、\`target.tag\`。

\`websocket\` 用于采集 WebSocket：

- 连接成功耗时：\`browser.websocket.connect.duration\`。
- 收发消息数：\`browser.websocket.message.count\`。
- 收发字节数：\`browser.websocket.message.bytes\`。
- 错误数：\`browser.websocket.error.count\`。

SDK 会忽略指向自身上报地址的 WebSocket URL。

## 7. 采集异常接口 body

\`httpBody\` 默认关闭。它会 patch \`fetch\` 和 \`XMLHttpRequest\`，只在请求失败、请求抛错或状态码 \`>= 400\` 时上报 body。

\`\`\`javascript
new BkOpenTelemetry({
  transport: {
    endpoint: 'https://bk-rum.tencent.com/',
  },
  plugins: {
    httpBody: {
      maxBodySize: 4 * 1024,
      redact: ({ body, type, url, status, truncated }) => {
        return body.replace(/password=[^&]+/g, 'password=***').replace(/token=[^&]+/g, 'token=***');
      },
    },
  },
});
\`\`\`

配置项：

- \`httpBody: true\`: 使用默认配置开启。
- \`httpBody.maxBodySize\`: 单个请求或响应 body 最大采集长度，默认 \`10 * 1024\` 字符。
- \`httpBody.redact\`: body 上报前的脱敏函数，必须返回字符串。

\`redact\` 入参：

- \`body\`: 已截断后的 body 字符串。
- \`type\`: \`request\` 或 \`response\`。
- \`url\`: 请求 URL。
- \`method\`: 请求方法。
- \`status\`: 响应状态码，网络错误时可能为空。
- \`contentType\`: body 的 content-type。
- \`truncated\`: 是否被 \`maxBodySize\` 截断。

建议只在排障需要时开启 \`httpBody\`，并务必处理密码、token、手机号等敏感信息。

## 8. 加公共属性和脱敏

公共属性适合放业务线、模块、页面类型等每条数据都想带上的信息。

\`\`\`javascript
new BkOpenTelemetry({
  transport: {
    endpoint: 'https://your-otlp-collector',
  },
  attributes: {
    page: () => ({
      'biz.module': 'order',
      'rum.page.host': location.host,
      'rum.page.path': location.pathname,
    }),
    metric: () => ({
      'biz.metric_source': 'rum',
    }),
    error: () => ({
      'biz.error_source': 'browser',
    }),
    custom: () => ({
      'biz.team': 'demo',
    }),
  },
  privacy: {
    redactUrl: url => url.replace(/token=[^&]+/g, 'token=***'),
    redactAttributes: attributes => {
      const next = { ...attributes };
      for (const key of Object.keys(next)) {
        if (typeof next[key] === 'string') {
          next[key] = next[key].replace(/\bd{11}\b/g, '***');
        }
      }
      return next;
    },
  },
});
\`\`\`

\`attributes\` 配置项：

- \`attributes.page\`: 页面、接口、资源、错误等 RUM 数据都会带上。
- \`attributes.metric\`: Web Vitals、Long Task、Route Timing、WebSocket 等 metric 会带上。
- \`attributes.error\`: JS 错误、白屏、CSP 等错误类数据会带上。
- \`attributes.custom\`: \`reportCustomEvent\` 上报的自定义事件会带上。

\`privacy\` 配置项：

- \`privacy.redactUrl\`: 处理 URL，例如 \`url.full\`、\`document.referrer\`、资源 URL。
- \`privacy.redactAttributes\`: 处理 span 和 log 属性。适合兜底清理敏感字段。
- \`plugins.httpBody.redact\`: 只处理请求和响应 body。

脱敏顺序可以简单理解为：URL 先走 \`redactUrl\`，属性整体再走 \`redactAttributes\`。

## 9. 配置设备和会话

\`device\` 和 \`session\` 默认开启，一般不需要配置。多应用共用同一域名时，可以自定义 storage key。

\`\`\`javascript
new BkOpenTelemetry({
  transport: {
    endpoint: 'https://your-otlp-collector',
  },
  plugins: {
    device: {
      storageKey: 'DEMO_DEVICE_ID',
    },
    session: {
      storageKey: 'DEMO_SESSION',
      inactivityMs: 30 * 60 * 1000,
      maxLifetimeMs: 24 * 60 * 60 * 1000,
    },
  },
});
\`\`\`

\`device\` 配置项：

- \`device: true\`: 使用默认设备配置。
- \`device.storageKey\`: 设备 ID 的 localStorage key，默认 \`BK_RUM_DEVICE_ID\`。
- 设备 ID 跨会话持久，会写入 \`device.id\`。

\`session\` 配置项：

- \`session: true\`: 使用默认会话配置。
- \`session.storageKey\`: 会话 storage key。默认会按上报 endpoint host 自动生成隔离后缀。
- \`session.inactivityMs\`: 用户不活跃多久后创建新会话，默认 \`30\` 分钟。
- \`session.maxLifetimeMs\`: 会话最长持续时间，默认 \`24\` 小时。

会话会写入 \`session.id\`，并在首次创建或轮换时上报 \`session.start\` / \`session.rotate\` log。

## 10. 手动上报业务事件

### 自定义事件

\`\`\`javascript
bkOT.reportCustomEvent({
  name: 'order.checkout',
  attributes: {
    'biz.order_id': 'O20260527001',
    'biz.order_amount': 199,
  },
});
\`\`\`

### 自定义失败事件

\`\`\`javascript
bkOT.reportCustomEvent({
  name: 'order.checkout',
  attributes: {
    'biz.order_id': 'O20260527001',
  },
  error: new Error('库存不足'),
});
\`\`\`

### 手动上报用户操作

\`\`\`javascript
bkOT.reportAction({
  type: 'click',
  targetText: '立即购买',
  targetTag: 'button',
  attributes: {
    'biz.order_id': 'O20260527001',
  },
});
\`\`\`

说明：

- \`reportCustomEvent.name\`: 事件名，会生成 \`custom.${name}\` span。
- \`reportCustomEvent.attributes\`: 业务属性，会和 \`attributes.custom\` 合并。
- \`reportCustomEvent.error\`: 传入后事件结果会标记为 error，并记录 exception。
- \`reportAction.type\`: 操作类型，会生成 \`action.\${type}\` span。
- 未命中采样时，手动上报事件会被静默丢弃；\`debug: true\` 时会打印提示。

## 11. 控制采样、调试和上报

\`\`\`javascript
new BkOpenTelemetry({
  debug: true,
  enabled: true,
  sampling: {
    rate: 0.2,
  },
  spanProcessor: 'batch',
  spanBatch: {
    maxQueueSize: 2048,
    maxExportBatchSize: 512,
    scheduledDelayMillis: 5000,
    exportTimeoutMillis: 30000,
  },
  transport: {
    endpoint: 'https://your-otlp-collector',
    token: 'your-report-token',
    headers: {
      'X-Biz-ID': 'demo',
    },
    signals: {
      traces: {
        timeoutMillis: 10000,
      },
      metrics: {
        concurrencyLimit: 2,
      },
    },
  },
});
\`\`\`

常用控制项：

- \`enabled\`: 是否启用 SDK，默认 \`true\`。设为 \`false\` 后不会启动采集和上报。
- \`debug\`: 是否在控制台输出 exporter 数据和插件异常，默认 \`false\`。
- \`sampling.rate\`: 采样率，范围 \`0 - 1\`，默认 \`1\`。
- \`spanProcessor\`: trace processor 模式，默认 \`batch\`。本地调试可用 \`simple\`。
- \`spanBatch\`: \`batch\` 模式的批量上报配置。
- \`transport.endpoint\`: OTLP collector 根地址，默认 \`http://localhost:4318\`。
- \`transport.token\`: 默认鉴权 token。
- \`transport.headers\`: 所有信号共用请求头。
- \`transport.signals.traces/metrics/logs\`: 分别配置某一类信号。

采样结果会在一次浏览器会话中保持稳定。\`rate < 1\` 时，SDK 会把采样结果写入 \`sessionStorage\`；不可用时降级到内存缓存。

如果三类信号要发到不同地址：

\`\`\`javascript
new BkOpenTelemetry({
  transport: {
    endpoint: 'https://your-otlp-collector',
    token: 'your-report-token',
    signals: {
      endpoints: {
        traces: 'https://trace.example.com/v1/traces',
        metrics: 'https://metric.example.com/v1/metrics',
        logs: 'https://log.example.com/v1/logs',
      },
    },
  },
});
\`\`\`

请求头优先级为：\`transport.token\` 默认头 < \`transport.headers\` < 单信号 \`headers\`。

## 12. 控制启动和生命周期

默认 \`autoStart: true\`。如果要先注册自定义插件或 instrumentation，再启动 SDK，可以关闭自动启动。

\`\`\`javascript
const bkOT = new BkOpenTelemetry({
  autoStart: false,
  transport: {
    endpoint: 'https://your-otlp-collector',
  },
});

await bkOT.start();
\`\`\`

生命周期方法：

\`\`\`javascript
await bkOT.flush();
await bkOT.shutdown();
\`\`\`

- \`start\`: 启动 provider、instrumentation 和插件。重复调用会直接返回。
- \`flush\`: 立即刷新插件、trace、metric、log。
- \`shutdown\`: 先刷新，再卸载插件、事件监听和 instrumentation。关闭后不能再次启动同一个实例。

## 13. 扩展插件

普通接入方通常不需要扩展插件。只有默认采集不满足时，再使用插件能力。

\`\`\`javascript
import { BkOpenTelemetry, createPlugin } from '@blueking/open-telemetry';

const plugin = createPlugin({
  name: 'demo-plugin',
  init(context) {
    context.setRuntimeAttributes({
      'biz.plugin_enabled': true,
    });

    const span = context.startSpan('demo.plugin_ready', {
      'biz.plugin': 'demo',
    });
    span.end();
  },
});

const bkOT = new BkOpenTelemetry({
  autoStart: false,
  plugins: {
    custom: [plugin],
  },
  transport: {
    endpoint: 'https://your-otlp-collector',
  },
});

await bkOT.start();
\`\`\`

也可以在 \`start()\` 前链式注册：

\`\`\`javascript
bkOT.use(plugin);
\`\`\`

插件上下文常用方法：

- \`context.startSpan\`: 创建 span。
- \`context.emitLog\`: 上报 log，并自动带上运行期公共属性和脱敏。
- \`context.meter\`: 创建 metric。
- \`context.setRuntimeAttributes\`: 更新后续数据都会携带的公共属性。
- \`context.getRuntimeAttributes\`: 获取当前公共属性快照。
- \`context.setUser\`: 更新用户上下文。
- \`context.setView\`: 更新 View 上下文。

## 14. 接入原生 OpenTelemetry Instrumentation

\`\`\`javascript
import { BkOpenTelemetry } from '@blueking/open-telemetry';
import { MyCustomInstrumentation } from './my-custom-instrumentation';

const bkOT = new BkOpenTelemetry({
  autoStart: false,
  instrumentations: {
    custom: [new MyCustomInstrumentation()],
  },
  transport: {
    endpoint: 'https://your-otlp-collector',
  },
});

await bkOT.start();
\`\`\`

也可以在 \`start()\` 前链式注册：

\`\`\`javascript
bkOT.useInstrumentation(new MyCustomInstrumentation());
\`\`\`

注意：\`use\` 和 \`useInstrumentation\` 必须在 \`start()\` 前调用。如果使用默认自动启动，请改成 \`autoStart: false\`。

## 15. 完整配置速查

\`\`\`javascript
new BkOpenTelemetry({
  app: {
    name: 'demo-app',
    environment: 'production',
    version: '1.0.0',
  },
  user: {
    id: 'user-001',
  },
  transport: {
    endpoint: 'https://your-otlp-collector',
    token: 'your-report-token',
    headers: {},
    signals: {
      endpoints: {
        traces: 'https://your-otlp-collector/v1/traces',
        metrics: 'https://your-otlp-collector/v1/metrics',
        logs: 'https://your-otlp-collector/v1/logs',
      },
      traces: {
        headers: {},
        timeoutMillis: 10000,
        concurrencyLimit: 2,
      },
      metrics: {},
      logs: {},
    },
  },
  enabled: true,
  autoStart: true,
  debug: false,
  sampling: {
    rate: 1,
  },
  spanProcessor: 'batch',
  spanBatch: {
    maxQueueSize: 2048,
    maxExportBatchSize: 512,
    scheduledDelayMillis: 5000,
    exportTimeoutMillis: 30000,
  },
  route: {
    getPathGroup: url => new URL(url, location.href).pathname,
  },
  attributes: {
    page: () => ({}),
    metric: () => ({}),
    error: () => ({}),
    custom: () => ({}),
  },
  privacy: {
    redactUrl: url => url,
    redactAttributes: attributes => attributes,
  },
  instrumentations: {
    documentLoad: true,
    fetch: true,
    xhr: true,
    userInteraction: true,
  },
  plugins: {
    pageView: true,
    resource: true,
    error: true,
    webVitals: true,
    blankScreen: true,
    device: true,
    session: true,
    action: false,
    httpBody: false,
    longTask: false,
    routeTiming: false,
    cspViolation: false,
    websocket: false,
  },
});
\`\`\`

配置默认值：

- \`autoStart\`: 默认 \`true\`。
- \`enabled\`: 默认 \`true\`。
- \`debug\`: 默认 \`false\`。
- \`sampling.rate\`: 默认 \`1\`。
- \`spanProcessor\`: 默认 \`batch\`。
- \`transport.endpoint\`: 默认 \`http://localhost:4318\`。
- \`app.environment\`: 默认 \`production\`。
- \`app.name\`: 默认 \`unknown_service\`。

## 16. 推荐接入顺序

新项目建议按下面顺序接入：

1. 先配置 \`app\`、\`transport\`、\`user\`，确认页面访问、错误、接口请求能上报。
2. 再配置 \`route.getPathGroup\`，避免 URL 动态 ID 导致维度过高。
3. 按业务需要开启 \`routeTiming\`、\`longTask\`、\`action\`、\`websocket\`。
4. 排障时再开启 \`httpBody\`，并先做好脱敏。
5. 最后补充 \`attributes\` 和 \`privacy\`，统一业务维度和敏感信息处理。
`;

export const AEGIS_MD = `# @tencent/aegis-web-sdk-v2

Aegis Web SDK v2 是Tencent OTeam开发用于 Web 页面的前端上报 SDK。它可以自动采集 PV、页面性能、Web Vitals、JS 错误、Promise 异常、资源加载错误、设备信息等数据，也支持按需开启接口测速、静态资源测速、SPA 路由、会话、白屏、WebSocket 等能力。

## 1. 安装和使用

### CDN 使用

\`\`\`html
<script src="https://aegis.cdn-go.cn/aegis-sdk-v2/latest/aegis.min.js"></script>
<script>
  window.AegisV2 = new Aegis({
    id: 'SDK-xxxxxx',
    hostUrl: {
      url: 'https://bk-aegis.tencent.com/collect',
    },
  });
</script>
\`\`\`

如果需要固定版本：

\`\`\`html
<script src="https://aegis.cdn-go.cn/aegis-sdk-v2/2.0.3/aegis.min.js"></script>
\`\`\`

如果需要指纹能力，可以使用：

\`\`\`html
<script src="https://aegis.cdn-go.cn/aegis-sdk-v2/latest/aegis.f.min.js"></script>
\`\`\`

### npm 使用

\`\`\`bash
npm install @tencent/aegis-web-sdk-v2
\`\`\`

\`\`\`javascript
import Aegis from '@tencent/aegis-web-sdk-v2';

const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
});

window.Aegis = aegis;
\`\`\`

\`id\` 是项目上报标识，通常从伽利略平台创建 Web 监控对象后获得。\`hostUrl.url\` 是上报地址，国内默认使用 \`https://bk-aegis.tencent.com/collect\`，海外可按需替换为 \`https://tgalileo.com/collect\`。

## 2. 默认采集

只配置 \`id\` 和 \`hostUrl.url\` 后，SDK 已经默认开启常用能力：

- \`pv\`: 页面访问上报。
- \`aid\`: 访问 ID，用于辅助识别一次访问。
- \`error\`: JS 错误、Promise 异常、静态资源加载错误。
- \`device\`: 设备、浏览器、屏幕等环境信息。
- \`close\`: 页面关闭时补充上报。
- \`pagePerformance\`: 页面加载性能和首屏时间。
- \`webVitals\`: FCP、LCP、CLS、INP 等体验指标。
- \`custom\`: 业务自定义日志、事件、测速。

默认关闭的能力需要手动打开：

- \`api\`: fetch / XMLHttpRequest 接口测速。
- \`assetSpeed\`: img、script、css、audio、video 等静态资源测速。
- \`spa\`: SPA 路由变化 PV。
- \`session\`: 会话、页面视图、用户操作链路。
- \`blankScreen\`: 白屏检测。
- \`websocket\`: WebSocket 上报。
- \`fId\`: 浏览器指纹，增强 UV 识别，但会增加性能开销。
- \`ie\`: IE 兼容补丁。

Web SDK 中 \`sendPvImmediately\` 默认是 \`true\`，PV 会尽量立即上报，避免被采样或节流影响。

## 3. 给数据加上用户和版本

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  uid: window.USER_ID,
  version: '1.0.0',
  env: 'production',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
});
\`\`\`

常用基础字段：

- \`uid\`: 用户 ID，便于按用户排查问题。
- \`version\`: 应用版本，便于定位某个版本的异常或性能变化。
- \`env\`: 运行环境，默认 \`production\`。非生产环境日志等级更详细。
- \`pageUrl\`: 手动指定当前页面地址。
- \`urlHandler\`: 全局页面 URL 处理函数，优先级高于 \`pageUrl\`，适合去掉动态参数或敏感参数。

运行中也可以更新配置：

\`\`\`javascript
aegis.setConfig({
  uid: 'user-001',
  version: '1.0.1',
});
\`\`\`

如果要补充当前页面快照信息：

\`\`\`javascript
aegis.updateSnapshootInfo({
  from: location.href,
  biz: {
    module: 'order',
  },
});
\`\`\`

## 4. 按需打开 SPA、接口和资源采集

多数 Web 应用建议先打开这三类能力：

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  plugin: {
    spa: {
      onRouterChange() {
        return {
          routeName: document.title,
          from: location.href,
        };
      },
    },
    api: true,
    assetSpeed: true,
  },
});
\`\`\`

- \`spa\`: 监听 \`pushState\`、\`replaceState\`、\`hashchange\`、\`popstate\`，路由变化时上报 PV。
- \`spa.onRouterChange\`: 路由变化时追加快照信息，适合补充路由名、业务模块等字段。
- \`api\`: 自动改写 \`fetch\` 和 \`XMLHttpRequest\`，采集接口耗时、状态码、retcode、请求链路信息。
- \`assetSpeed\`: 采集静态资源加载耗时和资源加载失败。

如果是传统多页应用，可以不开 \`spa\`，默认 \`pv\` 插件会在页面初始化时上报一次 PV。

## 5. 配置接口采集

接口采集默认只需要 \`api: true\`。如果要识别业务 retcode、采集请求响应详情或注入 trace header，可以改成对象配置：

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  plugin: {
    api: {
      reportWhenError: true,
      reportAbort: false,
      apiDetail: true,
      retCodeHandler(data) {
        const body = JSON.parse(data || '{}');
        return {
          code: body.code,
          isErr: body.code !== 0,
        };
      },
      reqParamHandler(body) {
        return typeof body === 'string' ? body.replace(/password=[^&]+/g, 'password=***') : body;
      },
      resBodyHandler(body) {
        return String(body).slice(0, 2000);
      },
      reqHeaders: ['x-request-id'],
      resHeaders: ['trace-id'],
      injectTraceHeader: 'traceparent',
      injectTraceUrls: [/^https://api.example.com/],
      injectTraceIgnoreUrls: [//login/],
      urlHandler(url) {
        return url.replace(//user/d+/, '/user/:id');
      },
      ignoreUrls: [//healthz/],
    },
  },
});
\`\`\`

\`plugin.api\` 常用配置：

- \`apiDetail\`: 是否采集请求参数和响应内容。建议只在需要排障时开启，并做好脱敏。
- \`retCodeHandler\`: 从响应体中解析业务返回码，返回 \`{ code, isErr }\`。
- \`reqParamHandler\`: 处理请求参数，可用于截断和脱敏。
- \`resBodyHandler\`: 处理响应体，可用于截断和脱敏。
- \`reqHeaders\`: 允许上报的请求头白名单。
- \`resHeaders\`: 允许上报的响应头白名单。
- \`reportWhenError\`: 接口异常是否强制上报，默认 \`true\`。
- \`reportAbort\`: XHR abort 是否上报，默认不报。
- \`resourceTypeHandler\`: 自定义 URL 类型判断，把某些请求识别为接口或静态资源。
- \`urlHandler\`: 上报前格式化 URL，适合去掉 query 或动态 ID。
- \`urlRewrite\`: SDK 改写请求前重写 URL，返回的新 URL 会真正用于请求。
- \`reportUrls\`: 只上报命中的接口。
- \`ignoreUrls\`: 不上报命中的接口。
- \`apiDetailReportUrls\`: 只对命中的接口采集详情。
- \`apiDetailIgnoreUrls\`: 不对命中的接口采集详情。
- \`injectTraceHeader\`: 注入链路请求头，可选 \`traceparent\`、\`b3\`、\`sw8\`、\`sentry-trace\`。
- \`injectTraceUrls\`: 只对命中的 URL 注入 trace header。
- \`injectTraceIgnoreUrls\`: 不对命中的 URL 注入 trace header。
- \`isSSE\`: 自定义判断是否为 SSE 请求。
- \`isFirstSSEChunk\`: 自定义判断首个 SSE chunk。

## 6. 配置页面性能和资源测速

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  plugin: {
    pagePerformance: {
      longtask: true,
      reportTimestamp: true,
    },
    assetSpeed: {
      urlHandler(url) {
        return url.split('?')[0];
      },
    },
  },
});
\`\`\`

- \`pagePerformance\`: 采集 DNS、TCP、SSL、TTFB、内容下载、DOM 解析、资源下载、首屏时间、FP 等指标。
- \`pagePerformance.longtask\`: 开启 Long Task 采集。
- \`pagePerformance.reportTimestamp\`: 为性能阶段附加起止时间戳，便于还原瀑布图。
- \`assetSpeed\`: 采集静态资源成功和失败日志。
- \`assetSpeed.urlHandler\`: 上报前处理资源 URL。

首屏计算支持两个 DOM 标记：

\`\`\`html
<div AEGIS-FIRST-SCREEN-TIMING>关键首屏内容</div>
<div AEGIS-IGNORE-FIRST-SCREEN-TIMING>不参与首屏计算的区域</div>
\`\`\`

- \`AEGIS-FIRST-SCREEN-TIMING\`: 指定关键首屏元素。
- \`AEGIS-IGNORE-FIRST-SCREEN-TIMING\`: 忽略该元素及其子元素。

## 7. 开启会话和用户操作链路

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  plugin: {
    session: {
      actionTypes: ['click', 'submit'],
      customActionNameAttribute: 'data-aegis-action',
      sessionExpiration: 15 * 60 * 1000,
      onSessionRebuild(sessionId) {
        console.log('session rebuilt:', sessionId);
      },
    },
  },
});
\`\`\`

\`plugin.session\` 会采集三层数据：\`session\`、\`view\`、\`action\`。

- \`actionTypes\`: 采集哪些用户操作。默认采集 \`click\`；传 \`false\` 或空数组可关闭 action。
- \`customActionNameAttribute\`: 从 DOM 属性中读取操作名称。
- \`sessionExpiration\`: 会话过期时间，默认 15 分钟。
- \`sessionGenerator\`: 自定义 session 生成逻辑，可返回字符串，也可返回链路信息对象。
- \`onSessionRebuild\`: 会话重建后的回调。

示例：

\`\`\`html
<button data-aegis-action="checkout_submit">提交订单</button>
\`\`\`

## 8. 开启白屏检测

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  plugin: {
    blankScreen: {
      containers: ['body', 'html', '#app', '#root', '.page-skeleton'],
      ignoreContainers: ['.ignore-blank'],
      emptyElementsPercent: 70,
      sameElementsPercent: 70,
      debounceDuration: 1500,
      reDetectInterval: 1500,
      everySideSampleNumber: 9,
    },
  },
});
\`\`\`

白屏检测会在 DOM 变化、错误发生、页面隐藏或关闭等时机检查页面采样点。

\`plugin.blankScreen\` 配置项：

- \`containers\`: 被认为是空白容器的选择器，默认 \`['body', 'html', '#app', '#root']\`。如果有骨架屏，建议加入骨架屏选择器。
- \`ignoreContainers\`: 忽略的容器选择器，用于减少误报。
- \`detectStartPosition\`: 采样起点，默认 \`{ x: 0, y: 0 }\`。
- \`emptyElementsPercent\`: 空白点比例阈值，默认 \`70\`。
- \`sameElementsPercent\`: 相同元素比例阈值，默认 \`70\`。
- \`debounceDuration\`: DOM 变化后的防抖时间，默认 \`1500\` ms。
- \`everySideSampleNumber\`: 每条边采样数量，默认 \`9\`。越高越准，也越耗时。
- \`disableSameElementsCheck\`: 是否关闭相同元素检测，默认 \`false\`。
- \`ignoreElesWhenDomChange\`: DOM 变化时忽略的元素。
- \`reDetectInterval\`: 首次命中白屏后复检间隔，默认 \`1500\` ms。

## 9. 手动上报业务日志、事件和测速

### 普通日志

\`\`\`javascript
aegis.info('进入订单页', { orderId: 'O20260527001' });
\`\`\`

### 业务告警日志

\`\`\`javascript
aegis.report('库存不足', {
  skuId: 'sku-001',
});
\`\`\`

### 自定义错误

\`\`\`javascript
aegis.error('支付失败', {
  code: 'PAY_TIMEOUT',
});
\`\`\`

### 自定义事件

\`\`\`javascript
aegis.reportEvent({
  name: 'order.checkout',
  from: location.href,
  orderId: 'O20260527001',
});
\`\`\`

也可以只传事件名：

\`\`\`javascript
aegis.reportEvent('order.checkout');
\`\`\`

### 自定义测速

\`\`\`javascript
aegis.time('order.submit');

await submitOrder();

aegis.timeEnd('order.submit', {
  orderId: 'O20260527001',
});
\`\`\`

如果已有耗时，可以直接上报：

\`\`\`javascript
aegis.reportTime('order.submit', 320);

aegis.reportTime({
  name: 'order.submit',
  duration: 320,
  from: location.href,
});
\`\`\`

\`reportTime\` 的 \`duration\` 单位是 ms，要求在 \`0 - 60000\` 之间。

## 10. 控制采样、压缩、重试和慢日志

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  sample: {
    pv: 1,
    error: 1,
    api: 0.5,
    assetSpeed: 0.2,
    session: 0.1,
  },
  repeat: 60,
  delay: 1000,
  maxLength: 100 * 1024,
  maxBatchReportLength: 400,
  compress: true,
  enableRetry: true,
  maxRetryCount: 3,
  forceReportErrorLog: true,
  forceReportSlowLog: {
    slowFirstScreenThreshold: 1800,
    slowResourceThreshold: 3000,
    slowApiThreshold: 5000,
  },
});
\`\`\`

常用上报控制项：

- \`sample\`: 采样率。可以是 \`0 - 1\` 的数字，也可以按插件配置，例如 \`{ api: 0.5 }\`。
- \`repeat\`: 重复上报限制，默认每分钟同类日志最多 \`60\` 次。
- \`delay\`: 延迟合并上报时间，默认 \`1000\` ms。
- \`maxLength\`: 单条日志最大长度，默认 \`100 * 1024\`。
- \`maxBatchReportLength\`: 单批最大上报条数，默认 \`400\`。
- \`compress\`: 是否开启 gzip 压缩，默认 \`false\`。
- \`enableRetry\`: 请求失败后是否重试，默认 \`false\`。
- \`maxRetryCount\`: 最大重试次数，默认 \`3\`。
- \`forceReportErrorLog\`: 错误日志是否不受采样影响，默认 \`false\`。
- \`forceReportSlowLog\`: 是否开启慢日志标记。传 \`true\` 使用默认阈值，也可以传对象自定义阈值。
- \`addXTopicKey\`: 是否在请求头中加入 \`X-Topic-Key\`。
- \`onSendFail\`: 重试耗尽后的失败回调。

慢日志默认阈值：

- \`slowFirstScreenThreshold\`: 慢首屏，默认 \`1800\` ms。
- \`slowResourceThreshold\`: 慢静态资源，默认 \`3000\` ms。
- \`slowApiThreshold\`: 慢接口，默认 \`5000\` ms。

## 11. 控制上报时机和生命周期

默认 \`reportImmediately: true\`，日志产生后即可进入上报流程。若业务需要等登录态、用户信息或初始化数据准备好后再发，可以关闭立即上报：

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  reportImmediately: false,
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
});

aegis.setConfig({
  uid: 'user-001',
});

aegis.ready();
\`\`\`

销毁 SDK：

\`\`\`javascript
await aegis.destroy();
\`\`\`

如果需要强制清空实例对象：

\`\`\`javascript
await aegis.destroy(true);
\`\`\`

其他实用方法：

- \`clearPluginCache()\`: 清空插件缓存。
- \`clearThrottleCache()\`: 清空节流缓存并触发一次发送。
- \`sendLogsImmediately(logs, options)\`: 立即发送指定日志。

## 12. 使用钩子处理数据

钩子适合做统一脱敏、过滤、调试或接入自定义链路。

\`\`\`javascript
const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  onBeforeSend(logs, aegis) {
    return logs.map(log => ({
      ...log,
      msg: String(log.msg).replace(/token=[^&s]+/g, 'token=***'),
    }));
  },
  onSendFail(logs, error, options) {
    console.warn('Aegis send failed:', error, options);
  },
});
\`\`\`

生命周期钩子：

- \`onNewAegis\`: 实例创建后触发。
- \`onConfigChange\`: \`setConfig\` 后触发。
- \`onBeforeDestroy\`: 销毁前触发。
- \`onDestroyed\`: 销毁后触发。
- \`onBeforeCollect\`: 日志采集前触发。
- \`onCollected\`: 日志采集后触发。
- \`onBeforeProcess\`: 日志处理前触发。
- \`onProcessed\`: 日志处理后触发。
- \`onBeforeSend\`: 上报前触发，可返回处理后的日志。
- \`onSended\`: 上报完成后触发。

## 13. 完整推荐配置

\`\`\`javascript
import Aegis from '@tencent/aegis-web-sdk-v2';

const aegis = new Aegis({
  id: 'SDK-xxxxxx',
  uid: window.USER_ID,
  version: '1.0.0',
  env: 'production',
  hostUrl: {
    url: 'https://bk-aegis.tencent.com/collect',
  },
  plugin: {
    pv: true,
    aid: true,
    error: true,
    device: true,
    close: true,
    pagePerformance: {
      reportTimestamp: true,
    },
    webVitals: true,
    spa: {
      onRouterChange() {
        return {
          routeName: document.title,
        };
      },
    },
    api: {
      apiDetail: false,
      reportWhenError: true,
      retCodeHandler(data) {
        try {
          const body = JSON.parse(data || '{}');
          return {
            code: body.code,
            isErr: body.code !== 0,
          };
        } catch (e) {
          return {
            code: 'unknown',
            isErr: false,
          };
        }
      },
      urlHandler(url) {
        return url.split('?')[0];
      },
      ignoreUrls: [//healthz/],
    },
    assetSpeed: {
      urlHandler(url) {
        return url.split('?')[0];
      },
    },
    session: {
      actionTypes: ['click'],
      customActionNameAttribute: 'data-aegis-action',
    },
    blankScreen: {
      containers: ['body', 'html', '#app', '#root'],
      ignoreContainers: ['.app-loading'],
    },
  },
  sample: 1,
  compress: true,
  enableRetry: true,
  maxRetryCount: 3,
  forceReportErrorLog: true,
  forceReportSlowLog: {
    slowFirstScreenThreshold: 1800,
    slowResourceThreshold: 3000,
    slowApiThreshold: 5000,
  },
  onBeforeSend(logs, aegis) {
    return logs;
  },
});

window.Aegis = aegis;
\`\`\`

## 14. 配置项速查

### 基础配置

- \`id\`: 必填，项目上报 ID。
- \`uid\`: 用户 ID。
- \`version\`: 应用版本。
- \`env\`: 环境，默认 \`production\`。
- \`hostUrl\`: 上报地址配置。字符串或对象均可，推荐对象写法。
- \`pageUrl\`: 手动指定页面 URL。
- \`urlHandler\`: 全局 URL 处理函数。
- \`extField\`: 额外扩展字段，会作为上报扩展信息发送。
- \`getNetworkType\`: Web 端自定义网络类型获取函数。
- \`getNetworkStatus\`: Web 端自定义网络状态获取函数。

### hostUrl 配置

- \`url\`: 主上报地址。
- \`whiteListUrl\`: 白名单和采样配置拉取地址。
- \`pvUrl\`: PV 上报地址。
- \`speedUrl\`: 接口和资源测速上报地址。
- \`performanceUrl\`: 页面性能上报地址。
- \`eventUrl\`: 自定义事件上报地址。
- \`webVitalsUrl\`: Web Vitals 上报地址。
- \`customTimeUrl\`: 自定义测速上报地址。
- \`pageUrl\`: 自定义页面 URL。

### plugin 配置

- \`pv\`: 页面访问上报，默认开启。
- \`aid\`: 访问 ID，默认开启。
- \`error\`: 错误采集，默认开启。
- \`device\`: 设备信息，默认开启。
- \`close\`: 页面关闭采集，默认开启。
- \`pagePerformance\`: 页面性能，默认开启。
- \`webVitals\`: Web Vitals，默认开启。
- \`custom\`: 自定义日志、事件、测速，默认开启。
- \`api\`: 接口测速，默认关闭。
- \`assetSpeed\`: 静态资源测速，默认关闭。
- \`spa\`: SPA 路由 PV，默认关闭。
- \`session\`: 会话和操作链路，默认关闭。
- \`blankScreen\`: 白屏检测，默认关闭。
- \`websocket\`: WebSocket 事件，默认关闭。
- \`fId\`: 浏览器指纹，默认关闭。
- \`ie\`: IE 补丁，默认关闭。

### 上报控制

- \`reportImmediately\`: 是否立即上报，默认 \`true\`。
- \`sendPvImmediately\`: 是否立即上报 PV。Web SDK 默认 \`true\`。
- \`whiteList\`: 是否启用白名单逻辑，默认 \`true\`。
- \`sample\`: 采样率，默认 \`1\`。
- \`repeat\`: 重复日志限制，默认 \`60\`。
- \`delay\`: 合并上报延迟，默认 \`1000\` ms。
- \`maxLength\`: 单条日志最大长度，默认 \`100 * 1024\`。
- \`maxBatchReportLength\`: 单批最大条数，默认 \`400\`。
- \`compress\`: 是否压缩，默认 \`false\`。
- \`enableRetry\`: 是否重试，默认 \`false\`。
- \`maxRetryCount\`: 最大重试次数，默认 \`3\`。
- \`forceReportErrorLog\`: 错误是否强制全量上报，默认 \`false\`。
- \`forceReportSlowLog\`: 是否标记慢首屏、慢资源、慢接口，默认 \`false\`。
- \`addXTopicKey\`: 是否添加 \`X-Topic-Key\` 请求头，默认 \`false\`。
`;
