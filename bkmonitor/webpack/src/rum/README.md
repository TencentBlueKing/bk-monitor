# @blueking/rum

`@blueking/rum`（即 `bk-ot`）是面向蓝鲸 RUM 场景的浏览器端 OpenTelemetry SDK。所有数据均以 OTLP/HTTP 协议发送至 OpenTelemetry Collector，并通过插件机制提供 Aegis 风格的 RUM 能力。

## Usage

```ts
import { initBkOT } from '@blueking/rum';

const bkOT = initBkOT({
  serviceName: 'demo-web',
  serviceVersion: '1.0.0',
  environment: 'production',
  endpoint: 'https://collector.example.com',
  headers: {
    Authorization: 'Bearer <token>',
  },
  sampleRate: 0.1,
  sampleStorageKey: '__demo_web_rum_sampled__',
  ignoreUrls: [/\/sockjs-node/, /\/__webpack_hmr/],
  propagateTraceHeaderUrls: [window.location.origin],
  resourceAttributes: {
    'bk.biz.id': '2',
  },
  getMetricAttributes: () => ({
    'bk.biz.id': '2',
  }),
  redactUrl: url => url.replace(/(token=)[^&]+/g, '$1[REDACTED]'),
  redactAttributes: attrs => {
    const next = { ...attrs };
    delete next['user.email'];
    return next;
  },
  instrumentations: {
    documentLoad: true,
    fetch: true,
    xhr: true,
    userInteraction: {
      eventNames: ['click', 'submit'],
    },
  },
  rum: {
    device: true,
    session: { inactivityMs: 30 * 60 * 1000 },
    pageView: true,
    error: { maxPerWindow: 5, windowMs: 60_000 },
    webVitals: true,
    blankScreen: true,
    websocket: true,
    longTask: { threshold: 50 },
    cspViolation: true,
    routeTiming: true,
  },
});

bkOT.reportBusinessEvent({
  name: 'dashboard.save',
  attributes: {
    'dashboard.panel.count': 12,
  },
});
```

## Signals

- HTTP 与文档加载时序由官方 OpenTelemetry 浏览器 instrumentation 收集。
- Page View / Device / Session / Web Vitals / Error / Blank Screen / WebSocket / Long Task / CSP Violation / Route Timing 通过独立 RUM 插件实现，可独立开关。
- 所有上报均使用 OpenTelemetry traces / metrics / logs，不再使用旧的 Aegis 日志包络。
- `sampleRate` 在每个浏览器会话内一次性决定，traces / metrics / logs / 业务事件共享同一采样结果。
- `ignoreUrls` 默认会排除 SDK 自身上报 endpoint，并允许用户继续过滤开发或健康检查请求。
- `propagateTraceHeaderUrls` 控制哪些请求会被注入 W3C Trace Context 头。

## 默认值与上线注意

| 字段                                                    | 默认值                      | 备注                                         |
| ------------------------------------------------------- | --------------------------- | -------------------------------------------- |
| `enabled`                                               | `true`                      | 接入层（如 monitor-pc）建议仅在生产启用      |
| `autoStart`                                             | `true`                      | 实例创建后立即 `start()`                     |
| `sampleRate`                                            | `1`（SDK 层），接入层 `0.1` | 接入层默认 10% 采样以保护后端                |
| `console`                                               | `false`                     | 设为 `true` 时所有上报数据会同步打印到控制台 |
| `metricIntervalMillis`                                  | `60_000`                    | metric 周期上报间隔                          |
| `rum.longTask` / `rum.cspViolation` / `rum.routeTiming` | `false`                     | 新增能力默认关闭，按需开启                   |

> 提示：`shutdown()` 之后不能再次 `start()` 同一个实例。如需重启请用 `createBkOT(...)` 创建新实例，避免使用已销毁的 provider/processor。

## Endpoint Rules

`endpoint` 既支持 Collector 根路径，也支持已经带有 `/v1` 的版本路径。

- `https://collector.example.com` 自动拼接为 `/v1/traces`、`/v1/metrics`、`/v1/logs`。
- `https://collector.example.com/v1` 自动拼接为 `/v1/traces`、`/v1/metrics`、`/v1/logs`。
- 可通过 `traces.endpoint`、`metrics.endpoint`、`logs.endpoint` 单独覆盖。
- `traces.headers` / `metrics.headers` / `logs.headers` 与根 `headers` 合并而非覆盖，便于按 signal 追加授权头。

## RUM 插件矩阵

| 插件          | Span                              | Metric                                                  | Log                   | 备注                                                        |
| ------------- | --------------------------------- | ------------------------------------------------------- | --------------------- | ----------------------------------------------------------- |
| device        | -                                 | -                                                       | -                     | 只写 runtime attributes（`device.id`、视口、网络）          |
| session       | -                                 | -                                                       | -                     | 只写 runtime attributes（`session.id`），含 30 分钟过期续期 |
| page-view     | `browser.page_view`               | -                                                       | -                     | 同 URL 自动去重                                             |
| error         | `browser.error` 等                | -                                                       | `severity=ERROR`      | 同 hash 错误窗口节流（默认 60s 内 5 条）                    |
| web-vitals    | `browser.web_vital`               | `browser.web_vital.cls`、`browser.web_vital.duration`   | -                     | metric 维度仅低基数；attribution 详情在 span                |
| blank-screen  | -                                 | `browser.blank_screen.count`                            | `severity=ERROR`      | DOMContentLoaded 后再检测，识别 loading mask                |
| websocket     | `websocket.connect`（仅连接阶段） | `browser.websocket.message.count` 等                    | `severity=ERROR/INFO` | 长连接不会卡住 span                                         |
| long-task     | -                                 | `browser.long_task.count`、`browser.long_task.duration` | -                     | 默认关闭                                                    |
| csp-violation | -                                 | -                                                       | `severity=WARN`       | 默认关闭                                                    |
| route-timing  | `browser.route_change`            | `browser.route_change.duration`                         | -                     | 双 raf 估算 SPA 路由切换耗时，默认关闭                      |

## Business Events

`initBkOT` 返回的实例提供 `reportBusinessEvent`：

```ts
bkOT.reportBusinessEvent({
  name: 'search.submit',
  attributes: {
    'search.keyword.length': 10,
  },
});
```

如事件失败，传入 error，对应的 span 会被标记为失败：

```ts
bkOT.reportBusinessEvent({
  name: 'dashboard.save.failed',
  error,
});
```

未命中采样时业务事件会被静默丢弃；启用 `console: true` 可在控制台看到对应提示。

## 隐私与脱敏

SDK 提供两个脱敏钩子，所有 RUM 自定义插件 emit 数据前会经过它们：

- `redactUrl(url) => string`：用于 `url.full`、`document.referrer`、`csp.blocked_uri` 等所有 URL 字段；
- `redactAttributes(attrs) => attrs`：作用于 `startSpan` 与 `emitLog` 的 attributes，可用于剔除自定义敏感字段。

接入层（如 `monitor-pc/open-telemetry.ts`）已默认对 `token`、`access_token`、`refresh_token`、`password`、`pwd`、`secret`、`auth`、`session`、`sessionid` 等常见敏感 query 参数做替换，业务可继续在 `bk_ot_config.redactUrl` 中追加规则。

## 自定义插件

```ts
import { createPlugin } from '@blueking/rum';

const myPlugin = createPlugin({
  name: 'my-plugin',
  enabled: true,
  init(context) {
    const span = context.startSpan('my.custom.span');
    span.end();
    context.emitLog({
      severityNumber: 9,
      severityText: 'INFO',
      body: 'custom log',
      attributes: { 'my.tag': 'foo' },
    });
  },
});

initBkOT({
  /* ... */
  plugins: [myPlugin],
});
```

`BkOTRuntimeContext` 提供：`tracer / meter / logger / startSpan / emitLog / applyRedact / getRuntimeAttributes / setRuntimeAttributes / config`，请优先使用 `startSpan` 与 `emitLog`，二者会自动叠加 runtime attributes 与 redact。
