# OpenTelemetry Web RUM 接入指引

> 面向第一次接触 OpenTelemetry 的前端开发。本文以浏览器端 Web RUM 为目标，介绍如何采集页面加载、接口请求、用户交互、Web Vitals、前端错误，并通过 OTLP HTTP 上报到 OpenTelemetry Collector 或自己的 RUM 网关。

## 1. 先理解几个概念

OpenTelemetry，简称 OT，是一套可观测性标准。它不是某一个监控平台，而是一套统一的数据采集、传输和语义规范。前端接入 OT 之后，可以把浏览器里的性能、请求、交互、错误等数据转换成统一格式，再发送给后端 Collector、APM、日志平台或 RUM 平台。

前端 RUM 常见采集对象：

| 类型       | 说明                                                                  | OpenTelemetry 中常见承载方式  |
| ---------- | --------------------------------------------------------------------- | ----------------------------- |
| 页面加载   | HTML 文档加载、静态资源加载、DNS/TCP/TTFB 等浏览器 Performance Timing | Trace Span                    |
| 接口请求   | `fetch`、`XMLHttpRequest` 请求耗时、状态码、错误                      | Trace Span                    |
| 用户交互   | 点击、提交、键盘等交互行为                                            | Trace Span                    |
| Web Vitals | CLS、FCP、INP、LCP、TTFB                                              | Metric，必要时也可以补充 Span |
| 前端异常   | `error`、`unhandledrejection`、业务主动上报错误                       | Trace Span 或 Log             |

一个新手可以先记住：

- Trace 用来回答“一次行为发生了什么、耗时多久、哪里慢了”。
- Metric 用来回答“某个指标整体趋势怎么样，比如 P75 LCP 是多少”。
- Resource 用来描述“这些数据来自哪个应用、哪个环境、哪个版本”。
- Collector 或 RUM 网关负责接收浏览器发来的 OTLP 数据，再转发到真正的存储和分析平台。

## 2. 当前官方最新 Web RUM 方案

本文按 2026-04-30 查询到的官方 npm latest 版本编写：

| 包                                                | 当前 latest | 用途                                      |
| ------------------------------------------------- | ----------- | ----------------------------------------- |
| `@opentelemetry/api`                              | `1.9.x`     | OT API，全局 Trace / Metric 入口          |
| `@opentelemetry/sdk-trace-web`                    | `2.7.1`     | 浏览器 Trace SDK                          |
| `@opentelemetry/sdk-metrics`                      | `2.7.1`     | Metric SDK                                |
| `@opentelemetry/resources`                        | `2.7.1`     | 设置 `service.name`、版本、环境等资源信息 |
| `@opentelemetry/exporter-trace-otlp-http`         | `0.216.0`   | 用 OTLP HTTP 上报 Trace                   |
| `@opentelemetry/exporter-metrics-otlp-http`       | `0.216.0`   | 用 OTLP HTTP 上报 Metric                  |
| `@opentelemetry/auto-instrumentations-web`        | `0.61.0`    | Web 自动埋点合集                          |
| `@opentelemetry/instrumentation-document-load`    | `0.61.0`    | 页面加载自动采集                          |
| `@opentelemetry/instrumentation-fetch`            | `0.216.0`   | `fetch` 自动采集                          |
| `@opentelemetry/instrumentation-xml-http-request` | `0.216.0`   | XHR 自动采集                              |
| `@opentelemetry/instrumentation-user-interaction` | `0.60.0`    | 用户交互自动采集                          |
| `web-vitals`                                      | `5.2.0`     | 官方 Web Vitals 指标采集库                |

需要特别注意：OpenTelemetry 官方文档明确说明浏览器端 Client Instrumentation 仍处于 experimental 阶段，部分包也标注为 experimental，未来小版本可能有破坏性变化。生产项目建议锁定版本并在升级前验证。

官方资料：

- OpenTelemetry Browser 指引：https://opentelemetry.io/docs/languages/js/getting-started/browser/
- OpenTelemetry JS 仓库：https://github.com/open-telemetry/opentelemetry-js
- OpenTelemetry JS Contrib 仓库：https://github.com/open-telemetry/opentelemetry-js-contrib
- web-vitals：https://github.com/GoogleChrome/web-vitals

## 3. 推荐整体架构

浏览器不建议直接把数据发到公网 Collector，也不要把平台 Token、鉴权密钥写在前端代码里。推荐使用同源 RUM 网关或后端代理。

```text
Browser
  |
  |  OTLP HTTP JSON
  |  /otel/v1/traces
  |  /otel/v1/metrics
  v
RUM Gateway / Backend Proxy
  |
  |  OTLP
  v
OpenTelemetry Collector
  |
  +--> Trace Backend
  +--> Metrics Backend
  +--> Logs / Event Backend
```

这样做有几个好处：

- 避免浏览器跨域、预检、鉴权暴露等问题。
- 可以在服务端统一补充租户、业务、地域等信息。
- 可以做采样、限流、字段清洗，避免前端异常流量打爆后端。
- 可以屏蔽不同后端平台的接入差异。

## 4. 安装依赖

如果项目使用 `pnpm`：

```bash
pnpm add @opentelemetry/api @opentelemetry/sdk-trace-web @opentelemetry/sdk-trace-base @opentelemetry/sdk-metrics @opentelemetry/resources @opentelemetry/semantic-conventions @opentelemetry/exporter-trace-otlp-http @opentelemetry/exporter-metrics-otlp-http @opentelemetry/auto-instrumentations-web @opentelemetry/context-zone web-vitals
```

如果你只想拆开手动注册每个 instrumentation，也可以安装：

```bash
pnpm add @opentelemetry/instrumentation @opentelemetry/instrumentation-document-load @opentelemetry/instrumentation-fetch @opentelemetry/instrumentation-xml-http-request @opentelemetry/instrumentation-user-interaction
```

新手建议优先使用 `@opentelemetry/auto-instrumentations-web`，它当前包含：

- `@opentelemetry/instrumentation-document-load`
- `@opentelemetry/instrumentation-fetch`
- `@opentelemetry/instrumentation-user-interaction`
- `@opentelemetry/instrumentation-xml-http-request`

## 5. 准备配置

可以先定义一个简单配置文件，便于区分不同环境。

```ts
// src/otel/otel-config.ts
export interface OtelRumConfig {
  serviceName: string;
  serviceVersion: string;
  environment: string;
  traceEndpoint: string;
  metricEndpoint: string;
  enabled: boolean;
}

export const otelRumConfig: OtelRumConfig = {
  serviceName: 'demo-web',
  serviceVersion: import.meta.env.VITE_APP_VERSION || '0.0.0',
  environment: import.meta.env.MODE,
  traceEndpoint: '/otel/v1/traces',
  metricEndpoint: '/otel/v1/metrics',
  enabled: import.meta.env.PROD,
};
```

如果你的项目不是 Vite，把 `import.meta.env` 换成项目自己的环境变量读取方式即可。

## 6. 初始化 Trace 自动采集

下面是一个可以直接参考的 `otel-rum.ts`。它会自动采集页面加载、资源加载、`fetch`、XHR、用户点击等 Trace。

```ts
// src/otel/otel-rum.ts
import { propagation } from '@opentelemetry/api';
import { W3CTraceContextPropagator } from '@opentelemetry/core';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { ATTR_SERVICE_NAME } from '@opentelemetry/semantic-conventions';

import { otelRumConfig } from './otel-config';

let traceProvider: WebTracerProvider | undefined;

const shouldPropagateTraceHeader = (url: string) => {
  const targetUrl = new URL(url, window.location.origin);

  // 只给同源接口或可信 API 域名注入 traceparent，避免把追踪头发给第三方。
  return targetUrl.origin === window.location.origin || targetUrl.hostname.endsWith('.example.com');
};

export const initOtelTrace = () => {
  if (!otelRumConfig.enabled || traceProvider) {
    return traceProvider;
  }

  const traceExporter = new OTLPTraceExporter({
    // 浏览器端 OTLP Trace endpoint 必须最终指向 /v1/traces。
    url: otelRumConfig.traceEndpoint,
    concurrencyLimit: 5,
  });

  traceProvider = new WebTracerProvider({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: otelRumConfig.serviceName,
      'service.version': otelRumConfig.serviceVersion,
      'deployment.environment.name': otelRumConfig.environment,
    }),
    spanProcessors: [
      new BatchSpanProcessor(traceExporter, {
        maxQueueSize: 100,
        maxExportBatchSize: 20,
        scheduledDelayMillis: 3000,
        exportTimeoutMillis: 10000,
      }),
    ],
  });

  traceProvider.register({
    contextManager: new ZoneContextManager(),
    propagator: new W3CTraceContextPropagator(),
  });

  propagation.setGlobalPropagator(new W3CTraceContextPropagator());

  registerInstrumentations({
    instrumentations: [
      getWebAutoInstrumentations({
        '@opentelemetry/instrumentation-document-load': {
          // 使用稳定 HTTP 语义约定，避免后续迁移成本。
          semconvStabilityOptIn: 'http',
        },
        '@opentelemetry/instrumentation-fetch': {
          semconvStabilityOptIn: 'http',
          propagateTraceHeaderCorsUrls: [shouldPropagateTraceHeader],
          clearTimingResources: true,
          ignoreUrls: [/\/otel\/v1\/traces/, /\/otel\/v1\/metrics/, /\/sockjs-node/, /\/__webpack_hmr/],
          applyCustomAttributesOnSpan: (span, request, result) => {
            span.setAttribute('rum.page.url', window.location.href);
            span.setAttribute('rum.page.path', window.location.pathname);

            if (result instanceof Error) {
              span.setAttribute('error.type', result.name);
              span.setAttribute('error.message', result.message);
            }

            if (request instanceof Request) {
              span.setAttribute('http.request.method', request.method);
            }
          },
        },
        '@opentelemetry/instrumentation-xml-http-request': {
          semconvStabilityOptIn: 'http',
          propagateTraceHeaderCorsUrls: [shouldPropagateTraceHeader],
          ignoreUrls: [/\/otel\/v1\/traces/, /\/otel\/v1\/metrics/, /\/sockjs-node/, /\/__webpack_hmr/],
        },
        '@opentelemetry/instrumentation-user-interaction': {
          eventNames: ['click', 'submit'],
        },
      }),
    ],
  });

  window.addEventListener('pagehide', () => {
    traceProvider?.forceFlush();
  });

  return traceProvider;
};
```

然后在应用入口尽早初始化：

```ts
// src/main.ts
import { initOtelTrace } from './otel/otel-rum';
import { initWebVitals } from './otel/web-vitals';
import { initBrowserErrorTracing } from './otel/browser-errors';

initOtelTrace();
initWebVitals();
initBrowserErrorTracing();

// 后面再初始化 Vue / React 应用
// createApp(App).mount('#app');
```

注意：OT 初始化应尽量早于应用渲染，否则首屏加载、首批接口请求可能采不到。

## 7. 上报 Web Vitals 指标

Web Vitals 是 Google 定义的一组用户体验核心指标。前端 RUM 通常至少需要上报：

| 指标 | 含义                                        | 单位   | 越小越好 |
| ---- | ------------------------------------------- | ------ | -------- |
| CLS  | Cumulative Layout Shift，累计布局偏移       | 无单位 | 是       |
| FCP  | First Contentful Paint，首次内容绘制        | ms     | 是       |
| INP  | Interaction to Next Paint，交互到下一次绘制 | ms     | 是       |
| LCP  | Largest Contentful Paint，最大内容绘制      | ms     | 是       |
| TTFB | Time to First Byte，首字节时间              | ms     | 是       |

Web Vitals 更适合用 Metric 上报，因为平台通常会按 P75、P90、P95 聚合分析。

```ts
// src/otel/web-vitals.ts
import { metrics } from '@opentelemetry/api';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { ATTR_SERVICE_NAME } from '@opentelemetry/semantic-conventions';
import { onCLS, onFCP, onINP, onLCP, onTTFB } from 'web-vitals/attribution';

import { otelRumConfig } from './otel-config';

let meterProvider: MeterProvider | undefined;

const getNavigationType = () => {
  const navigationEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;

  return navigationEntry?.type || 'unknown';
};

const getPageAttributes = () => ({
  'rum.page.path': window.location.pathname,
  'rum.page.host': window.location.host,
  'rum.navigation.type': getNavigationType(),
});

export const initWebVitals = () => {
  if (!otelRumConfig.enabled || meterProvider) {
    return meterProvider;
  }

  const metricExporter = new OTLPMetricExporter({
    // 浏览器端 OTLP Metric endpoint 必须最终指向 /v1/metrics。
    url: otelRumConfig.metricEndpoint,
    concurrencyLimit: 1,
  });

  meterProvider = new MeterProvider({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: otelRumConfig.serviceName,
      'service.version': otelRumConfig.serviceVersion,
      'deployment.environment.name': otelRumConfig.environment,
    }),
    readers: [
      new PeriodicExportingMetricReader({
        exporter: metricExporter,
        exportIntervalMillis: 10000,
        exportTimeoutMillis: 10000,
      }),
    ],
  });

  metrics.setGlobalMeterProvider(meterProvider);

  const meter = meterProvider.getMeter('web-vitals');

  const clsHistogram = meter.createHistogram('browser.web_vital.cls', {
    description: 'Cumulative Layout Shift',
    unit: '1',
  });

  const durationHistogram = meter.createHistogram('browser.web_vital.duration', {
    description: 'Web Vitals duration metrics, including FCP, INP, LCP and TTFB',
    unit: 'ms',
  });

  onCLS(metric => {
    clsHistogram.record(metric.value, {
      ...getPageAttributes(),
      'web_vital.name': metric.name,
      'web_vital.rating': metric.rating,
    });
  });

  const recordDurationMetric = metric => {
    durationHistogram.record(metric.value, {
      ...getPageAttributes(),
      'web_vital.name': metric.name,
      'web_vital.rating': metric.rating,
    });
  };

  onFCP(recordDurationMetric);
  onINP(recordDurationMetric);
  onLCP(recordDurationMetric);
  onTTFB(recordDurationMetric);

  window.addEventListener('pagehide', () => {
    meterProvider?.forceFlush();
  });

  return meterProvider;
};
```

不要把 `metric.id`、完整 URL、用户 ID 这类高基数字段直接放到 Metric attributes 里。Metric 是要聚合的，标签维度越多，时序数量越多，存储和查询成本越高。建议保留稳定低基数字段，例如：

- `rum.page.path`
- `rum.page.host`
- `rum.navigation.type`
- `web_vital.name`
- `web_vital.rating`
- `service.name`
- `service.version`
- `deployment.environment.name`

如果你确实需要排查某一次具体 Web Vitals 事件，可以额外创建 Trace Span 或事件日志，把 `metric.id`、`metric.attribution` 放进去，但不要放在 Metric labels 里。

## 8. 可选：把 Web Vitals 也写成 Span

Metric 适合看趋势，Span 适合看单次细节。如果你的后端 Trace 平台更方便排查单次页面问题，可以同时写入一个短 Span。

```ts
// src/otel/web-vitals-span.ts
import { trace } from '@opentelemetry/api';
import { onCLS, onINP, onLCP } from 'web-vitals/attribution';

const tracer = trace.getTracer('web-vitals');

const recordWebVitalSpan = metric => {
  const span = tracer.startSpan(`web-vital.${metric.name}`);

  span.setAttributes({
    'web_vital.name': metric.name,
    'web_vital.value': metric.value,
    'web_vital.rating': metric.rating,
    'web_vital.id': metric.id,
    'rum.page.path': window.location.pathname,
  });

  if (metric.attribution) {
    span.setAttribute('web_vital.attribution', JSON.stringify(metric.attribution));
  }

  span.end();
};

export const initWebVitalSpans = () => {
  onCLS(recordWebVitalSpan);
  onINP(recordWebVitalSpan);
  onLCP(recordWebVitalSpan);
};
```

这个方案不建议替代 Metric，只建议作为排查辅助。

## 9. 采集前端异常

OpenTelemetry JS 浏览器自动埋点目前主要覆盖加载、请求、交互，并不会完整替代 Sentry 这类错误监控。可以先用手动 Span 采集全局错误。

```ts
// src/otel/browser-errors.ts
import { SpanStatusCode, trace } from '@opentelemetry/api';

const tracer = trace.getTracer('browser-errors');

const normalizeReason = (reason: unknown) => {
  if (reason instanceof Error) {
    return {
      name: reason.name,
      message: reason.message,
      stack: reason.stack,
    };
  }

  return {
    name: typeof reason,
    message: String(reason),
    stack: undefined,
  };
};

export const initBrowserErrorTracing = () => {
  window.addEventListener('error', event => {
    const span = tracer.startSpan('browser.error');

    span.setAttributes({
      'exception.type': event.error?.name || 'Error',
      'exception.message': event.message,
      'exception.stacktrace': event.error?.stack || '',
      'rum.page.path': window.location.pathname,
      'rum.error.source': 'window.error',
    });

    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: event.message,
    });

    span.end();
  });

  window.addEventListener('unhandledrejection', event => {
    const error = normalizeReason(event.reason);
    const span = tracer.startSpan('browser.unhandledrejection');

    span.setAttributes({
      'exception.type': error.name,
      'exception.message': error.message,
      'exception.stacktrace': error.stack || '',
      'rum.page.path': window.location.pathname,
      'rum.error.source': 'unhandledrejection',
    });

    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error.message,
    });

    span.end();
  });
};
```

如果项目里已经有错误平台，可以不要重复上报完整堆栈，只上报错误 ID、错误类型、页面路径，避免敏感信息泄露。

## 10. SPA 路由切换怎么处理

自动埋点可以采集页面初次加载，但 SPA 页面切换通常不会触发完整文档加载。对于 Vue Router / React Router 这类前端路由，需要手动记录路由切换。

Vue Router 示例：

```ts
// src/otel/router-tracing.ts
import { trace } from '@opentelemetry/api';
import type { Router } from 'vue-router';

const tracer = trace.getTracer('router');

export const installRouterTracing = (router: Router) => {
  router.beforeEach((to, from) => {
    const span = tracer.startSpan('router.navigation');

    span.setAttributes({
      'router.from': from.fullPath,
      'router.to': to.fullPath,
      'rum.page.path': to.path,
    });

    to.meta.__otelNavigationSpan = span;
  });

  router.afterEach(to => {
    const span = to.meta.__otelNavigationSpan;

    span?.end();
  });

  router.onError((error, to) => {
    const span = to.meta.__otelNavigationSpan;

    span?.recordException(error);
    span?.setAttribute('error.message', error.message);
    span?.end();
  });
};
```

实际项目里不要直接扩展 `RouteMeta` 的未知字段，建议补充类型声明：

```ts
// src/types/vue-router.d.ts
import type { Span } from '@opentelemetry/api';

declare module 'vue-router' {
  interface RouteMeta {
    __otelNavigationSpan?: Span;
  }
}
```

## 11. 后端接收要求

### 11.1 Endpoint 路径

OTLP HTTP 对路径有明确约定：

- Trace endpoint 需要是 `/v1/traces`
- Metric endpoint 需要是 `/v1/metrics`

如果前端配置的是同源代理：

```ts
traceEndpoint: '/otel/v1/traces',
metricEndpoint: '/otel/v1/metrics',
```

后端代理需要把它们转发到 Collector：

```text
/otel/v1/traces  ->  http://otel-collector:4318/v1/traces
/otel/v1/metrics ->  http://otel-collector:4318/v1/metrics
```

### 11.2 CORS

如果浏览器直接请求 Collector，Collector 或网关必须允许跨域：

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins:
            - https://your-web.example.com
          allowed_headers:
            - content-type
            - traceparent
            - tracestate
```

生产环境建议优先使用同源后端代理，少直接开放 Collector。

### 11.3 采样和限流

前端 RUM 数据量通常很大，建议至少做三层控制：

- 前端按用户、会话或页面做采样，例如只采 10% 会话。
- RUM 网关按应用和租户做限流。
- Collector 再做 tail sampling、属性过滤、批量发送。

前端简单采样示例：

```ts
const shouldEnableRum = () => {
  const sampleRate = 0.1;
  const storageKey = 'rum-sampled';
  const cached = sessionStorage.getItem(storageKey);

  if (cached) {
    return cached === '1';
  }

  const sampled = Math.random() < sampleRate;
  sessionStorage.setItem(storageKey, sampled ? '1' : '0');

  return sampled;
};
```

## 12. Trace Context 透传

当你启用 `fetch` 或 XHR 的 `propagateTraceHeaderCorsUrls` 后，浏览器请求会带上 W3C Trace Context 请求头：

```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

后端服务如果也接入了 OpenTelemetry，就能把“用户点击按钮 -> 前端请求 -> 后端接口 -> 数据库查询”串成一条链路。

注意事项：

- 只给自己控制的接口注入 `traceparent`。
- 跨域接口必须允许 `traceparent`、`tracestate` 请求头。
- 不要给第三方统计、广告、支付、地图等外部域名注入追踪头。

## 13. 如何验证是否接入成功

本地或测试环境可以按下面步骤验证：

1. 打开浏览器 DevTools 的 Network 面板。
2. 刷新页面。
3. 观察是否有 `/otel/v1/traces` 请求。
4. 等待 10 秒左右，观察是否有 `/otel/v1/metrics` 请求。
5. 点击页面按钮或触发接口请求，确认后续 Trace 请求仍然上报。
6. 在后端 Collector 或监控平台里搜索 `service.name = demo-web`。

如果没有看到请求，优先检查：

- `otelRumConfig.enabled` 是否为 `true`。
- 初始化是否足够早。
- endpoint 是否正确。
- Network 里是否被 CORS 拦截。
- 是否被 `ignoreUrls` 过滤。
- 是否还没有达到批量上报时间。

## 14. 常见问题

### 14.1 为什么页面打开后没有立刻上报？

Trace 使用 `BatchSpanProcessor`，Metric 使用 `PeriodicExportingMetricReader`，它们都会批量发送。这样可以减少网络请求，对页面性能更友好。如果调试时想更快看到数据，可以临时缩短 `scheduledDelayMillis` 和 `exportIntervalMillis`。

### 14.2 可以直接在前端写鉴权 Token 吗？

不建议。前端代码和请求都可以被用户看到，Token 一旦泄露就可能被滥用。推荐同源 RUM 网关，由服务端加鉴权信息并转发到 Collector 或监控平台。

### 14.3 Web Vitals 为什么要用 Metric，不直接用 Trace？

Web Vitals 的核心价值是聚合分析，比如按页面看 P75 LCP、按版本看 INP 是否变差。Metric 更适合这类统计。Trace 可以保留个别样本用于排查，但不适合作为唯一上报方式。

### 14.4 为什么不能把完整 URL 当 Metric 标签？

完整 URL 可能包含 query、ID、搜索词等高基数字段，也可能包含敏感信息。Metric 标签维度过高会导致时序爆炸，增加成本并拖慢查询。建议只使用标准化后的路由路径，例如 `/alarm/detail/:id`。

### 14.5 为什么有些接口没有关联到后端链路？

常见原因：

- `propagateTraceHeaderCorsUrls` 没匹配到接口域名。
- 后端没有接入 OpenTelemetry。
- 跨域配置没有允许 `traceparent`。
- 网关把 `traceparent` 请求头过滤掉了。

### 14.6 `ZoneContextManager` 一定要用吗？

不是绝对必须，但浏览器里很多异步行为依赖它来维持上下文，用户交互和异步请求串联时更有帮助。官方文档也在 Web 示例里使用了 `ZoneContextManager`。需要注意，官方包说明里提到它对目标为 ES2017+ 的代码存在限制，如果项目遇到上下文丢失或兼容问题，需要单独验证构建目标和浏览器支持情况。

## 15. 生产接入建议清单

上线前建议检查：

- 已确认使用当前官方 latest 包，并锁定依赖版本。
- 前端只上报到同源 RUM 网关或可信 Collector。
- 没有在前端暴露监控平台密钥。
- 已配置采样和限流。
- Trace endpoint 以 `/v1/traces` 结束。
- Metric endpoint 以 `/v1/metrics` 结束。
- `ignoreUrls` 已排除 OT 上报接口、HMR、静态资源热更新接口。
- `propagateTraceHeaderCorsUrls` 只匹配可信后端域名。
- Metric attributes 没有用户 ID、完整 URL、订单 ID、搜索词等高基数字段。
- 错误堆栈、URL query、接口参数已做敏感信息清洗。
- 已验证页面加载、接口请求、用户交互、Web Vitals、错误事件都能被后端看到。

## 16. 最小可用版本总结

如果只想最快跑通，至少需要三步：

1. 初始化 `WebTracerProvider`，用 `OTLPTraceExporter` 上报到 `/v1/traces`。
2. 注册 `getWebAutoInstrumentations()`，采集页面加载、请求、交互。
3. 初始化 `MeterProvider`，用 `web-vitals` 采集 CLS、FCP、INP、LCP、TTFB，并用 `OTLPMetricExporter` 上报到 `/v1/metrics`。

最小入口示例：

```ts
import { initOtelTrace } from './otel/otel-rum';
import { initWebVitals } from './otel/web-vitals';

initOtelTrace();
initWebVitals();
```

到这里，你已经完成了一个符合当前 OpenTelemetry 官方 Web RUM 方向的基础接入方案。后续可以根据业务需要继续补充路由、错误、业务关键操作、用户会话 ID、采样策略和数据脱敏规则。
