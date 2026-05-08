# 使用 OpenTelemetry 接入蓝鲸监控前端 RUM 指引

> 本文面向第一次接触 OpenTelemetry 的前端开发。你可以把它理解成一份“照着做就能把浏览器监控数据上报到蓝鲸监控平台”的接入手册。

## 1. 你将接入什么

接入完成后，用户在浏览器里访问你的前端页面时，页面会自动采集并上报这些前端监控数据到蓝鲸监控平台：

| 数据类型       | 能看到什么问题                           | 示例                                        |
| -------------- | ---------------------------------------- | ------------------------------------------- |
| 页面加载性能   | 页面打开慢、静态资源慢、首屏慢           | HTML 加载、JS/CSS/图片资源加载耗时          |
| 接口请求       | 哪些接口慢、哪些接口失败                 | `fetch` / `XMLHttpRequest` 请求耗时、状态码 |
| 用户交互       | 用户点击后发生了什么、交互是否触发慢接口 | 点击按钮、提交表单                          |
| Web Vitals     | 页面体验是否健康                         | CLS、FCP、INP、LCP、TTFB                    |
| 前端异常       | 页面脚本报错、Promise 未捕获错误         | `window.error`、`unhandledrejection`        |
| 自定义业务事件 | 关键业务行为是否发生                     | 下单、搜索、保存配置、打开弹窗              |

本文使用的是 OpenTelemetry 官方 Web 生态的当前最新方案：

- 使用 `@opentelemetry/sdk-trace-web` 初始化浏览器 Trace。
- 使用 `@opentelemetry/auto-instrumentations-web` 自动采集页面加载、请求和交互。
- 使用 `@opentelemetry/sdk-metrics` 和 `web-vitals` 上报核心 Web Vitals 指标。
- 使用 OTLP HTTP 协议把数据发给蓝鲸监控平台提供的接入地址。

## 2. 先理解 5 个基础概念

### 2.1 OpenTelemetry 是什么

OpenTelemetry，简称 OT，是一套开源可观测性标准。它负责定义“数据怎么采集、叫什么字段、用什么协议发出去”。蓝鲸监控平台负责接收、存储、分析和展示这些数据。

你可以这样理解：

```text
你的前端页面
  |
  | 使用 OpenTelemetry SDK 采集数据
  v
OTLP HTTP 上报
  |
  v
蓝鲸监控平台
  |
  v
查看页面性能、接口请求、Web Vitals、异常和链路
```

### 2.2 Trace 是什么

Trace 表示一次完整行为的调用链。前端里最常见的是：

- 页面加载产生一个页面加载 Trace。
- 用户点击按钮产生一个用户交互 Span。
- 点击后发起接口请求，接口请求也会产生 Span。

如果后端也接入了 OpenTelemetry，并且前端请求带上 `traceparent`，蓝鲸监控平台就可以把“前端点击 -> 前端请求 -> 后端接口 -> 数据库或下游服务”串起来。

### 2.3 Span 是什么

Span 是 Trace 里的一个片段，表示某一步操作。比如：

- 加载 HTML 文档是一个 Span。
- 加载一张图片是一个 Span。
- 发起一次 `fetch` 请求是一个 Span。
- 用户点击一次按钮是一个 Span。

Span 通常会带上开始时间、结束时间、耗时、状态和属性。

### 2.4 Metric 是什么

Metric 是指标数据，适合做趋势统计，比如：

- 某个页面的 P75 LCP 是多少。
- 这个版本上线后 INP 有没有变差。
- 某个页面的 CLS 是否超过健康阈值。

Web Vitals 更适合用 Metric 上报，因为蓝鲸监控平台可以按页面、版本、环境等维度聚合分析。

### 2.5 Resource 是什么

Resource 用来说明这些监控数据来自哪个应用。接入时至少要设置：

- `service.name`：应用名称。
- `service.version`：应用版本。
- `deployment.environment.name`：环境，比如 `production`、`staging`、`test`。

蓝鲸监控平台可以用这些字段区分不同业务、环境和版本。

## 3. 当前最新官方版本

本文按 2026-04-30 查询到的 npm latest 版本编写：

| 包名                                              | latest 版本 | 用途                           |
| ------------------------------------------------- | ----------- | ------------------------------ |
| `@opentelemetry/api`                              | `1.9.x`     | OpenTelemetry API              |
| `@opentelemetry/sdk-trace-web`                    | `2.7.1`     | 浏览器 Trace SDK               |
| `@opentelemetry/sdk-trace-base`                   | `2.7.1`     | Span Processor、采样等基础能力 |
| `@opentelemetry/sdk-metrics`                      | `2.7.1`     | Metric SDK                     |
| `@opentelemetry/resources`                        | `2.7.1`     | 设置应用资源信息               |
| `@opentelemetry/semantic-conventions`             | `1.40.0`    | 语义化字段常量                 |
| `@opentelemetry/exporter-trace-otlp-http`         | `0.216.0`   | Trace OTLP HTTP 上报           |
| `@opentelemetry/exporter-metrics-otlp-http`       | `0.216.0`   | Metric OTLP HTTP 上报          |
| `@opentelemetry/auto-instrumentations-web`        | `0.61.0`    | Web 自动埋点合集               |
| `@opentelemetry/instrumentation-document-load`    | `0.61.0`    | 页面加载自动采集               |
| `@opentelemetry/instrumentation-fetch`            | `0.216.0`   | `fetch` 自动采集               |
| `@opentelemetry/instrumentation-xml-http-request` | `0.216.0`   | XHR 自动采集                   |
| `@opentelemetry/instrumentation-user-interaction` | `0.60.0`    | 用户交互自动采集               |
| `@opentelemetry/context-zone`                     | `2.7.1`     | 浏览器异步上下文管理           |
| `web-vitals`                                      | `5.2.0`     | Web Vitals 指标采集            |

重要说明：

- OpenTelemetry 官方文档目前仍提示 Browser Client Instrumentation 是 experimental。
- `@opentelemetry/exporter-*-otlp-http`、`@opentelemetry/instrumentation-fetch` 等包也标注为 experimental，可能在小版本里出现破坏性变化。
- 生产项目建议锁定版本，升级前先在测试环境验证。

官方资料：

- OpenTelemetry Browser 文档：https://opentelemetry.io/docs/languages/js/getting-started/browser/
- OpenTelemetry JS：https://github.com/open-telemetry/opentelemetry-js
- OpenTelemetry JS Contrib：https://github.com/open-telemetry/opentelemetry-js-contrib
- web-vitals：https://github.com/GoogleChrome/web-vitals

## 4. 上报到蓝鲸监控的整体流程

蓝鲸监控平台会提供前端 RUM 的 OTLP HTTP 接入地址。本文先使用暂定占位地址：

```ts
const BK_OTEL_TRACE_URL = 'https://bk-monitor.example.com/otel/v1/traces';
const BK_OTEL_METRIC_URL = 'https://bk-monitor.example.com/otel/v1/metrics';
```

实际接入时，请替换成蓝鲸监控平台提供的真实地址。

推荐流程：

```text
用户浏览器
  |
  | OTLP HTTP JSON
  | Trace:  /v1/traces
  | Metric: /v1/metrics
  v
蓝鲸监控前端 RUM 接入地址
  |
  v
蓝鲸监控平台
  |
  v
页面性能、接口请求、Web Vitals、异常、链路分析
```

如果你的公司内网有统一网关，也可以先上报到同源代理，再由代理转发到蓝鲸监控平台：

```text
用户浏览器 -> 业务同源网关 -> 蓝鲸监控平台
```

这种方式可以避免浏览器跨域问题，也能在服务端统一加鉴权信息。

## 5. 接入前准备

你需要准备 4 类信息：

| 配置项               | 示例                                             | 说明                           |
| -------------------- | ------------------------------------------------ | ------------------------------ |
| 蓝鲸 Trace 上报 URL  | `https://bk-monitor.example.com/otel/v1/traces`  | 上报 Trace 数据                |
| 蓝鲸 Metric 上报 URL | `https://bk-monitor.example.com/otel/v1/metrics` | 上报 Web Vitals 等指标         |
| 应用名称             | `mall-web`                                       | 用于蓝鲸监控里区分应用         |
| 应用版本             | `1.0.0`                                          | 用于分析版本变更影响           |
| 环境                 | `production`                                     | 用于区分生产、预发布、测试环境 |

如果蓝鲸监控平台要求额外参数，例如应用 ID、空间 ID、Token、数据源 ID，请优先按平台提供的方式配置。不要把长期有效的敏感密钥直接写在前端代码中。

## 6. 安装依赖

如果你的项目使用 `pnpm`，执行：

```bash
pnpm add @opentelemetry/api @opentelemetry/sdk-trace-web @opentelemetry/sdk-trace-base @opentelemetry/sdk-metrics @opentelemetry/resources @opentelemetry/semantic-conventions @opentelemetry/exporter-trace-otlp-http @opentelemetry/exporter-metrics-otlp-http @opentelemetry/auto-instrumentations-web @opentelemetry/context-zone web-vitals
```

如果你的项目使用 `npm`，执行：

```bash
npm install @opentelemetry/api @opentelemetry/sdk-trace-web @opentelemetry/sdk-trace-base @opentelemetry/sdk-metrics @opentelemetry/resources @opentelemetry/semantic-conventions @opentelemetry/exporter-trace-otlp-http @opentelemetry/exporter-metrics-otlp-http @opentelemetry/auto-instrumentations-web @opentelemetry/context-zone web-vitals
```

如果你的项目使用 `yarn`，执行：

```bash
yarn add @opentelemetry/api @opentelemetry/sdk-trace-web @opentelemetry/sdk-trace-base @opentelemetry/sdk-metrics @opentelemetry/resources @opentelemetry/semantic-conventions @opentelemetry/exporter-trace-otlp-http @opentelemetry/exporter-metrics-otlp-http @opentelemetry/auto-instrumentations-web @opentelemetry/context-zone web-vitals
```

## 7. 推荐文件结构

建议把 OpenTelemetry 相关代码单独放在一个目录里：

```text
src/
  otel/
    bk-rum-config.ts
    bk-rum-trace.ts
    bk-rum-web-vitals.ts
    bk-rum-errors.ts
    bk-rum-business.ts
    index.ts
```

每个文件负责一类事情：

| 文件                   | 职责                           |
| ---------------------- | ------------------------------ |
| `bk-rum-config.ts`     | 管理蓝鲸监控上报地址和应用信息 |
| `bk-rum-trace.ts`      | 初始化 Trace SDK 和自动埋点    |
| `bk-rum-web-vitals.ts` | 采集并上报 Web Vitals          |
| `bk-rum-errors.ts`     | 采集前端异常                   |
| `bk-rum-business.ts`   | 提供业务自定义事件上报方法     |
| `index.ts`             | 对外暴露统一初始化方法         |

## 8. 第一步：创建配置文件

创建 `src/otel/bk-rum-config.ts`：

```ts
// src/otel/bk-rum-config.ts
export interface BkRumConfig {
  enabled: boolean;
  serviceName: string;
  serviceVersion: string;
  environment: string;
  traceUrl: string;
  metricUrl: string;
  sampleRate: number;
  propagateTraceHeaderUrls: Array<string | RegExp>;
}

const getEnvValue = (key: string, fallback = '') => {
  // Vite 项目可以使用 import.meta.env；Webpack 项目可以换成 process.env。
  return import.meta.env?.[key] || fallback;
};

export const bkRumConfig: BkRumConfig = {
  // 建议先在测试环境打开，验证无误后再打开生产环境。
  enabled: getEnvValue('VITE_BK_RUM_ENABLED', 'true') === 'true',

  // 应用标识。建议使用蓝鲸监控平台中登记的应用名称。
  serviceName: getEnvValue('VITE_BK_RUM_SERVICE_NAME', 'demo-web'),

  // 应用版本。推荐接入 CI/CD，在构建时注入 commit hash 或版本号。
  serviceVersion: getEnvValue('VITE_APP_VERSION', '0.0.0'),

  // 环境名称，例如 production、staging、test。
  environment: getEnvValue('VITE_APP_ENV', import.meta.env.MODE || 'production'),

  // 暂定上报地址。实际接入时替换为蓝鲸监控平台提供的地址。
  traceUrl: getEnvValue('VITE_BK_RUM_TRACE_URL', 'https://bk-monitor.example.com/otel/v1/traces'),
  metricUrl: getEnvValue('VITE_BK_RUM_METRIC_URL', 'https://bk-monitor.example.com/otel/v1/metrics'),

  // 采样率：1 表示 100% 上报，0.1 表示 10% 用户会话上报。
  sampleRate: Number(getEnvValue('VITE_BK_RUM_SAMPLE_RATE', '1')),

  // 只有匹配这些地址的请求才会注入 traceparent。
  propagateTraceHeaderUrls: [window.location.origin, /^https:\/\/api\.example\.com/],
};
```

你需要根据自己的项目替换：

- `demo-web`
- `https://bk-monitor.example.com/otel/v1/traces`
- `https://bk-monitor.example.com/otel/v1/metrics`
- `https://api.example.com`

## 9. 第二步：增加采样控制

如果你的访问量很大，建议不要一开始就 100% 上报。可以按浏览器会话采样：同一个用户本次打开页面时，要么一直上报，要么一直不上报。

```ts
// src/otel/bk-rum-config.ts
export const isBkRumSampled = () => {
  const storageKey = '__bk_rum_sampled__';
  const cached = sessionStorage.getItem(storageKey);

  if (cached) {
    return cached === '1';
  }

  const normalizedSampleRate = Math.max(0, Math.min(1, bkRumConfig.sampleRate));
  const sampled = Math.random() < normalizedSampleRate;

  sessionStorage.setItem(storageKey, sampled ? '1' : '0');

  return sampled;
};
```

如果是刚接入测试环境，可以先设置：

```env
VITE_BK_RUM_SAMPLE_RATE=1
```

生产环境建议结合访问量调整，例如：

```env
VITE_BK_RUM_SAMPLE_RATE=0.1
```

## 10. 第三步：初始化 Trace 自动采集

创建 `src/otel/bk-rum-trace.ts`：

```ts
// src/otel/bk-rum-trace.ts
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

import { bkRumConfig, isBkRumSampled } from './bk-rum-config';

let traceProvider: WebTracerProvider | undefined;

const shouldPropagateTraceHeader = (url: string) => {
  const requestUrl = new URL(url, window.location.origin);

  return bkRumConfig.propagateTraceHeaderUrls.some(pattern => {
    if (typeof pattern === 'string') {
      return requestUrl.href.startsWith(pattern);
    }

    return pattern.test(requestUrl.href);
  });
};

export const initBkRumTrace = () => {
  if (!bkRumConfig.enabled || !isBkRumSampled() || traceProvider) {
    return traceProvider;
  }

  const traceExporter = new OTLPTraceExporter({
    // 蓝鲸监控平台提供的 Trace OTLP HTTP 接入地址，必须指向 /v1/traces。
    url: bkRumConfig.traceUrl,
    concurrencyLimit: 5,
  });

  traceProvider = new WebTracerProvider({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: bkRumConfig.serviceName,
      'service.version': bkRumConfig.serviceVersion,
      'deployment.environment.name': bkRumConfig.environment,
      'telemetry.sdk.language': 'webjs',
      'rum.provider': 'blueking',
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
          // 使用稳定 HTTP 语义约定，避免后续字段迁移成本。
          semconvStabilityOptIn: 'http',
        },
        '@opentelemetry/instrumentation-fetch': {
          semconvStabilityOptIn: 'http',
          propagateTraceHeaderCorsUrls: [shouldPropagateTraceHeader],
          ignoreUrls: [/\/v1\/traces/, /\/v1\/metrics/, /\/sockjs-node/, /\/__webpack_hmr/],
          applyCustomAttributesOnSpan: span => {
            span.setAttribute('rum.page.host', window.location.host);
            span.setAttribute('rum.page.path', window.location.pathname);
          },
        },
        '@opentelemetry/instrumentation-xml-http-request': {
          semconvStabilityOptIn: 'http',
          propagateTraceHeaderCorsUrls: [shouldPropagateTraceHeader],
          ignoreUrls: [/\/v1\/traces/, /\/v1\/metrics/, /\/sockjs-node/, /\/__webpack_hmr/],
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

这段代码会自动采集：

- 页面文档加载。
- 页面静态资源加载。
- `fetch` 请求。
- `XMLHttpRequest` 请求。
- 用户点击和表单提交。

## 11. 第四步：上报 Web Vitals

创建 `src/otel/bk-rum-web-vitals.ts`：

```ts
// src/otel/bk-rum-web-vitals.ts
import { metrics } from '@opentelemetry/api';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { ATTR_SERVICE_NAME } from '@opentelemetry/semantic-conventions';
import { onCLS, onFCP, onINP, onLCP, onTTFB } from 'web-vitals/attribution';

import { bkRumConfig, isBkRumSampled } from './bk-rum-config';

let meterProvider: MeterProvider | undefined;

const getNavigationType = () => {
  const navigationEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;

  return navigationEntry?.type || 'unknown';
};

const getCommonAttributes = () => ({
  'rum.page.host': window.location.host,
  'rum.page.path': window.location.pathname,
  'rum.navigation.type': getNavigationType(),
});

export const initBkRumWebVitals = () => {
  if (!bkRumConfig.enabled || !isBkRumSampled() || meterProvider) {
    return meterProvider;
  }

  const metricExporter = new OTLPMetricExporter({
    // 蓝鲸监控平台提供的 Metric OTLP HTTP 接入地址，必须指向 /v1/metrics。
    url: bkRumConfig.metricUrl,
    concurrencyLimit: 1,
  });

  meterProvider = new MeterProvider({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: bkRumConfig.serviceName,
      'service.version': bkRumConfig.serviceVersion,
      'deployment.environment.name': bkRumConfig.environment,
      'telemetry.sdk.language': 'webjs',
      'rum.provider': 'blueking',
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

  const meter = meterProvider.getMeter('bk-rum-web-vitals');

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
      ...getCommonAttributes(),
      'web_vital.name': metric.name,
      'web_vital.rating': metric.rating,
    });
  });

  const recordDurationMetric = (metric: { name: string; value: number; rating: string }) => {
    durationHistogram.record(metric.value, {
      ...getCommonAttributes(),
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

### 11.1 Web Vitals 指标说明

| 指标 | 中文说明         | 单位   | 建议关注                       |
| ---- | ---------------- | ------ | ------------------------------ |
| CLS  | 累计布局偏移     | 无单位 | 页面是否突然抖动、按钮是否位移 |
| FCP  | 首次内容绘制     | ms     | 用户多久看到第一个内容         |
| INP  | 交互到下一次绘制 | ms     | 用户点击后页面响应是否及时     |
| LCP  | 最大内容绘制     | ms     | 首屏主要内容多久出现           |
| TTFB | 首字节时间       | ms     | 服务端和网络响应是否慢         |

### 11.2 为什么 Web Vitals 用 Metric 上报

Web Vitals 更适合看聚合趋势，比如：

- 某个页面最近 1 小时 P75 LCP 是否超过阈值。
- 新版本发布后 INP 是否变差。
- 某个环境的 CLS 是否异常。

所以示例里使用了 `MeterProvider` 和 Histogram。蓝鲸监控平台可以基于这些指标做页面维度、版本维度、环境维度的聚合分析。

### 11.3 不建议放进 Metric 标签的字段

Metric 的标签维度不能太多。不要把下面这些字段作为 Metric attributes：

- 用户 ID。
- 订单 ID。
- 完整 URL。
- 带 query 的 URL。
- 搜索词。
- 错误堆栈。
- `web-vitals` 的 `metric.id`。

推荐保留这些低基数字段：

- `service.name`
- `service.version`
- `deployment.environment.name`
- `rum.page.host`
- `rum.page.path`
- `rum.navigation.type`
- `web_vital.name`
- `web_vital.rating`

## 12. 第五步：采集前端异常

创建 `src/otel/bk-rum-errors.ts`：

```ts
// src/otel/bk-rum-errors.ts
import { SpanStatusCode, trace } from '@opentelemetry/api';

import { bkRumConfig, isBkRumSampled } from './bk-rum-config';

const tracer = trace.getTracer('bk-rum-errors');

const normalizeError = (error: unknown) => {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack || '',
    };
  }

  return {
    name: typeof error,
    message: String(error),
    stack: '',
  };
};

export const initBkRumErrors = () => {
  if (!bkRumConfig.enabled || !isBkRumSampled()) {
    return;
  }

  window.addEventListener('error', event => {
    const error = normalizeError(event.error);
    const span = tracer.startSpan('browser.error');

    span.setAttributes({
      'exception.type': error.name,
      'exception.message': event.message || error.message,
      'exception.stacktrace': error.stack,
      'rum.page.host': window.location.host,
      'rum.page.path': window.location.pathname,
      'rum.error.source': 'window.error',
      'rum.error.filename': event.filename || '',
      'rum.error.lineno': event.lineno || 0,
      'rum.error.colno': event.colno || 0,
    });

    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: event.message || error.message,
    });

    span.end();
  });

  window.addEventListener('unhandledrejection', event => {
    const error = normalizeError(event.reason);
    const span = tracer.startSpan('browser.unhandledrejection');

    span.setAttributes({
      'exception.type': error.name,
      'exception.message': error.message,
      'exception.stacktrace': error.stack,
      'rum.page.host': window.location.host,
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

注意：错误堆栈可能包含敏感信息。生产环境建议结合蓝鲸监控平台的字段清洗能力，或在前端做必要脱敏。

## 13. 第六步：上报自定义业务事件

自动埋点只能采集通用行为。如果你想上报业务关键事件，例如“用户点击保存”“搜索失败”“下单成功”，可以封装一个自定义方法。

创建 `src/otel/bk-rum-business.ts`：

```ts
// src/otel/bk-rum-business.ts
import { SpanStatusCode, trace } from '@opentelemetry/api';

import { bkRumConfig, isBkRumSampled } from './bk-rum-config';

const tracer = trace.getTracer('bk-rum-business');

export interface BkRumBusinessEvent {
  name: string;
  attributes?: Record<string, string | number | boolean>;
  error?: Error;
}

export const reportBkRumBusinessEvent = ({ name, attributes = {}, error }: BkRumBusinessEvent) => {
  if (!bkRumConfig.enabled || !isBkRumSampled()) {
    return;
  }

  const span = tracer.startSpan(`business.${name}`);

  span.setAttributes({
    ...attributes,
    'rum.page.host': window.location.host,
    'rum.page.path': window.location.pathname,
    'rum.business.name': name,
  });

  if (error) {
    span.recordException(error);
    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error.message,
    });
  }

  span.end();
};
```

使用示例：

```ts
import { reportBkRumBusinessEvent } from '@/otel/bk-rum-business';

const handleSearch = async (keyword: string) => {
  reportBkRumBusinessEvent({
    name: 'search.submit',
    attributes: {
      // 不建议上报完整搜索词，这里只上报长度，避免泄露用户输入。
      'search.keyword.length': keyword.length,
    },
  });

  try {
    await searchApi(keyword);
  } catch (error) {
    reportBkRumBusinessEvent({
      name: 'search.failed',
      error: error as Error,
    });
  }
};
```

自定义业务事件建议遵守这些规则：

- 事件名使用稳定英文，例如 `search.submit`、`order.create`。
- 不要上报手机号、邮箱、身份证号、Token、完整搜索词。
- 不要把用户 ID、订单 ID 等高基数字段放到 Metric 标签里。
- 如果确实需要排查单个用户问题，优先使用蓝鲸监控平台推荐的用户标识字段和脱敏规则。

## 14. 第七步：统一初始化

创建 `src/otel/index.ts`：

```ts
// src/otel/index.ts
import { initBkRumErrors } from './bk-rum-errors';
import { initBkRumTrace } from './bk-rum-trace';
import { initBkRumWebVitals } from './bk-rum-web-vitals';

let initialized = false;

export const initBkRum = () => {
  if (initialized) {
    return;
  }

  initialized = true;

  initBkRumTrace();
  initBkRumWebVitals();
  initBkRumErrors();
};
```

然后在你的应用入口尽早调用。

Vue 示例：

```ts
// src/main.ts
import { createApp } from 'vue';
import App from './App.vue';
import { initBkRum } from './otel';

initBkRum();

createApp(App).mount('#app');
```

React 示例：

```tsx
// src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { initBkRum } from './otel';

initBkRum();

ReactDOM.createRoot(document.getElementById('root')!).render(<App />);
```

为什么要尽早调用？因为页面加载、首屏接口、首屏资源都发生得很早。如果等页面渲染完再初始化，首屏数据可能已经丢失。

## 15. 可选：SPA 路由切换上报

单页应用不会在路由切换时重新加载 HTML，所以自动页面加载采集只能覆盖首次打开。你可以手动上报路由切换。

Vue Router 示例：

```ts
// src/otel/bk-rum-router.ts
import { Span, SpanStatusCode, trace } from '@opentelemetry/api';
import type { Router } from 'vue-router';

const tracer = trace.getTracer('bk-rum-router');
const routeSpanMap = new WeakMap<object, Span>();

export const installBkRumRouter = (router: Router) => {
  router.beforeEach((to, from) => {
    const span = tracer.startSpan('router.navigation');

    span.setAttributes({
      'router.from.path': from.path,
      'router.to.path': to.path,
      'rum.page.path': to.path,
    });

    routeSpanMap.set(to, span);
  });

  router.afterEach(to => {
    const span = routeSpanMap.get(to);

    span?.end();
  });

  router.onError((error, to) => {
    const span = routeSpanMap.get(to);

    span?.recordException(error);
    span?.setStatus({
      code: SpanStatusCode.ERROR,
      message: error.message,
    });
    span?.end();
  });
};
```

入口使用：

```ts
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { initBkRum } from './otel';
import { installBkRumRouter } from './otel/bk-rum-router';

initBkRum();
installBkRumRouter(router);

createApp(App).use(router).mount('#app');
```

## 16. Trace Context 透传到后端

如果后端也接入了 OpenTelemetry，前端请求应该带上 `traceparent` 请求头。这样蓝鲸监控平台才能看到完整链路。

示例请求头：

```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

前面的 `bkRumConfig.propagateTraceHeaderUrls` 控制哪些请求可以带这个头：

```ts
propagateTraceHeaderUrls: [
  window.location.origin,
  /^https:\/\/api\.example\.com/,
],
```

请注意：

- 只给你自己控制的后端接口注入 `traceparent`。
- 不要给第三方 SDK、广告、地图、支付、统计接口注入。
- 如果接口跨域，后端需要允许 `traceparent` 和 `tracestate` 请求头。

后端 CORS 需要允许：

```http
Access-Control-Allow-Headers: traceparent, tracestate, content-type
```

## 17. 蓝鲸监控上报 URL 要求

OTLP HTTP 对路径有固定约定：

| 数据   | URL 后缀      |
| ------ | ------------- |
| Trace  | `/v1/traces`  |
| Metric | `/v1/metrics` |

所以蓝鲸监控平台提供的地址通常会类似：

```text
https://bk-monitor.example.com/otel/v1/traces
https://bk-monitor.example.com/otel/v1/metrics
```

如果平台只提供一个基础地址，例如：

```text
https://bk-monitor.example.com/otel
```

那么前端配置时需要拼成：

```ts
traceUrl: 'https://bk-monitor.example.com/otel/v1/traces',
metricUrl: 'https://bk-monitor.example.com/otel/v1/metrics',
```

如果蓝鲸监控平台提供的是业务同源代理地址，也同样要保持最终路径语义：

```ts
traceUrl: '/bk-rum/v1/traces',
metricUrl: '/bk-rum/v1/metrics',
```

由后端代理转发到蓝鲸监控平台即可。

## 18. 如何验证接入成功

打开浏览器 DevTools，按下面步骤检查。

### 18.1 看浏览器请求

1. 打开 Network 面板。
2. 刷新页面。
3. 搜索 `v1/traces`。
4. 搜索 `v1/metrics`。
5. 点击页面按钮或触发接口请求，再观察是否继续上报。

正常情况下你会看到：

```text
POST https://bk-monitor.example.com/otel/v1/traces
POST https://bk-monitor.example.com/otel/v1/metrics
```

### 18.2 看请求状态码

| 状态          | 说明                   |
| ------------- | ---------------------- |
| `200` / `202` | 上报成功               |
| `204`         | 上报成功，无响应体     |
| `400`         | 请求格式不符合接入要求 |
| `401` / `403` | 鉴权失败               |
| `404`         | 上报 URL 错误          |
| CORS error    | 跨域配置不正确         |

### 18.3 在蓝鲸监控平台检查

进入蓝鲸监控平台后，可以按这些字段搜索：

- `service.name = demo-web`
- `service.version = 1.0.0`
- `deployment.environment.name = production`
- `rum.provider = blueking`
- `web_vital.name = LCP`

如果 Trace 有数据，但 Web Vitals 没有数据，通常是 Metric 上报地址或 Metric 接收配置有问题。

如果 Web Vitals 有数据，但接口请求没有链路，通常是 `propagateTraceHeaderUrls`、CORS 或后端 Trace 接入有问题。

## 19. 常见问题

### 19.1 为什么我看不到上报请求

先检查：

- `VITE_BK_RUM_ENABLED` 是否是 `true`。
- `sampleRate` 是否太低。
- `initBkRum()` 是否在应用入口调用。
- 是否在本地环境被你主动关闭。
- 浏览器是否阻止了请求。

### 19.2 为什么页面打开后不是马上上报

Trace 和 Metric 都默认批量上报，目的是减少浏览器网络请求。示例里：

- Trace 每 `3000ms` 左右批量发送一次。
- Metric 每 `10000ms` 左右批量发送一次。

如果页面很快关闭，代码里通过 `pagehide` 做了 `forceFlush()`，尽量在离开页面前把数据发出去。

### 19.3 为什么上报接口跨域失败

如果你直接上报到蓝鲸监控平台域名，平台侧需要允许你的站点 Origin。需要确认：

- `Access-Control-Allow-Origin` 包含你的前端域名。
- `Access-Control-Allow-Headers` 包含 `content-type`、`traceparent`、`tracestate`。
- `Access-Control-Allow-Methods` 包含 `POST`、`OPTIONS`。

如果无法调整跨域配置，建议使用业务同源代理。

### 19.4 能不能把蓝鲸鉴权 Token 写在前端

不建议。前端代码和请求都可以被用户看到，长期有效 Token 写在前端有泄露风险。建议：

- 使用蓝鲸监控平台提供的前端专用接入凭证。
- 或使用业务后端代理，由后端加鉴权信息。
- 或使用短期签名机制。

### 19.5 为什么 Web Vitals 的数据和 Lighthouse 不完全一样

Lighthouse 是实验室环境模拟，Web Vitals 是真实用户浏览器环境采集。真实用户的网络、设备、浏览器、页面停留时间都不同，所以两者不一定完全一致。

RUM 更适合回答“真实用户体验怎么样”，Lighthouse 更适合回答“可优化项有哪些”。

### 19.6 为什么不建议上报完整 URL

完整 URL 可能包含：

- 用户 ID。
- 订单 ID。
- 搜索词。
- Token。
- 邮箱或手机号。

同时完整 URL 基数很高，会让 Metric 时序数量暴涨。建议上报标准化路径，例如：

```text
/order/detail/:id
/search
/user/profile
```

## 20. 生产上线检查清单

上线前建议逐项确认：

- 已替换为蓝鲸监控平台提供的真实 `traceUrl` 和 `metricUrl`。
- Trace URL 最终指向 `/v1/traces`。
- Metric URL 最终指向 `/v1/metrics`。
- `service.name` 使用蓝鲸监控平台登记的应用名。
- `service.version` 能区分不同发布版本。
- `deployment.environment.name` 能区分生产、预发布、测试环境。
- 生产环境设置了合适的 `sampleRate`。
- 没有把长期有效密钥写入前端代码。
- `propagateTraceHeaderUrls` 只包含可信后端域名。
- `ignoreUrls` 已排除 OT 上报地址，避免自己采集自己。
- Metric attributes 没有用户 ID、订单 ID、完整 URL、搜索词等高基数字段。
- 错误信息和业务事件已经做敏感信息控制。
- 在蓝鲸监控平台能看到 Trace、Web Vitals Metric、前端异常。

## 21. 最小接入总结

如果你只想最快完成接入，需要做 4 件事：

1. 安装 OpenTelemetry Web 相关依赖和 `web-vitals`。
2. 配置蓝鲸监控平台提供的 Trace URL 和 Metric URL。
3. 在应用入口调用 `initBkRum()`。
4. 打开浏览器 Network 和蓝鲸监控平台确认数据是否上报成功。

最小入口代码：

```ts
import { initBkRum } from './otel';

initBkRum();
```

接入完成后，蓝鲸监控平台就可以接收到你的前端页面性能、接口请求、用户交互、Web Vitals 和异常数据。后续可以根据业务需要继续补充路由切换、自定义业务事件、用户会话标识和更精细的采样策略。
