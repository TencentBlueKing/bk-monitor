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

import type { BkOTPlugin } from './plugin';
import type { Attributes } from '@opentelemetry/api';

export type BkOTAttributeValue = boolean | number | string;

export interface BkOTBatchConfig {
  exportTimeoutMillis?: number;
  maxExportBatchSize?: number;
  maxQueueSize?: number;
  scheduledDelayMillis?: number;
}

export interface BkOTBusinessEventPayload {
  attributes?: Attributes;
  error?: Error;
  name: string;
}

export interface BkOTConfig {
  autoStart?: boolean;
  console?: boolean;
  enabled?: boolean;
  endpoint?: string;
  environment?: string;
  headers?: Record<string, string>;
  ignoreUrls?: UrlMatcher[];
  instrumentations?: BkOTInstrumentationsConfig;
  logs?: Partial<SignalExporterConfig>;
  metricIntervalMillis?: number;
  metrics?: Partial<SignalExporterConfig>;
  plugins?: BkOTPlugin[];
  propagateTraceHeaderUrls?: UrlMatcher[];
  resourceAttributes?: Attributes;
  rum?: BkOTRumConfig;
  sampleRate?: number;
  sampleStorageKey?: string;
  serviceName: string;
  serviceVersion?: string;
  spanBatch?: BkOTBatchConfig;
  traces?: Partial<SignalExporterConfig>;
  getBusinessAttributes?: () => Attributes;
  getErrorAttributes?: () => Attributes;
  getMetricAttributes?: () => Attributes;
  getPageAttributes?: () => Attributes;
  // 用于隐私脱敏：在所有 RUM 自定义插件 emit 之前过滤一次属性
  redactAttributes?: (attributes: Attributes) => Attributes;
  // 用于隐私脱敏：所有上报到 attribute 的 URL 在写入前会经过此函数
  redactUrl?: (url: string) => string;
}

export interface BkOTHttpBodyConfig {
  maxBodySize?: number;
  redact?: (payload: BkOTHttpBodyRedactPayload) => string;
}

export interface BkOTHttpBodyRedactPayload {
  body: string;
  contentType?: string;
  method: string;
  status?: number;
  truncated: boolean;
  type: 'request' | 'response';
  url: string;
}

export interface BkOTInstrumentationsConfig {
  documentLoad?: boolean;
  fetch?: boolean;
  userInteraction?: boolean | { eventNames?: string[] };
  xhr?: boolean;
}

export interface BkOTRumConfig {
  cspViolation?: boolean;
  device?: boolean | { storageKey?: string };
  httpBody?: BkOTHttpBodyConfig | boolean;
  pageView?: boolean;
  routeTiming?: boolean;
  websocket?: boolean;
  webVitals?: boolean;
  blankScreen?:
    | {
        checkDelay?: number;
        // 自定义"页面已渲染"忽略选择器，命中即认为是 loading 占位、非空白
        ignoreSelectors?: string[];
        rootSelector?: string;
        threshold?: number;
      }
    | boolean;
  error?:
    | {
        // 同 hash 错误窗口内最多上报多少条，默认 5
        maxPerWindow?: number;
        // 节流窗口长度（ms），默认 60_000
        windowMs?: number;
      }
    | boolean;
  longTask?:
    | {
        // 任务时长阈值（ms），低于该值的 longtask 不上报，默认 50
        threshold?: number;
      }
    | boolean;
  session?:
    | {
        // 不活跃多久后视为新会话，默认 30 分钟
        inactivityMs?: number;
        storageKey?: string;
      }
    | boolean;
}

export interface NormalizedBkOTConfig
  extends Omit<
    BkOTConfig,
    | 'autoStart'
    | 'console'
    | 'enabled'
    | 'endpoint'
    | 'environment'
    | 'getBusinessAttributes'
    | 'getErrorAttributes'
    | 'getMetricAttributes'
    | 'getPageAttributes'
    | 'ignoreUrls'
    | 'logs'
    | 'metrics'
    | 'propagateTraceHeaderUrls'
    | 'redactAttributes'
    | 'redactUrl'
    | 'sampleStorageKey'
    | 'traces'
  > {
  autoStart: boolean;
  console: boolean;
  enabled: boolean;
  endpoint: string;
  environment: string;
  ignoreUrls: UrlMatcher[];
  logs: SignalExporterConfig;
  metricIntervalMillis: number;
  metrics: SignalExporterConfig;
  propagateTraceHeaderUrls: UrlMatcher[];
  resourceAttributes: Attributes;
  sampleRate: number;
  sampleStorageKey: string;
  traces: SignalExporterConfig;
  getBusinessAttributes: () => Attributes;
  getErrorAttributes: () => Attributes;
  getMetricAttributes: () => Attributes;
  getPageAttributes: () => Attributes;
  redactAttributes: (attributes: Attributes) => Attributes;
  redactUrl: (url: string) => string;
  instrumentations: Required<Pick<BkOTInstrumentationsConfig, 'documentLoad' | 'fetch' | 'xhr'>> & {
    userInteraction: BkOTInstrumentationsConfig['userInteraction'];
  };
  rum: Omit<Required<BkOTRumConfig>, 'httpBody'> & {
    httpBody: false | Required<BkOTHttpBodyConfig>;
  };
}

export interface SignalExporterConfig {
  concurrencyLimit?: number;
  endpoint: string;
  headers?: Record<string, string>;
  timeoutMillis?: number;
}

export type UrlMatcher = ((url: string) => boolean) | RegExp | string;

const DEFAULT_OTLP_ENDPOINT = 'http://localhost:4318';

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const resolveSignalEndpoint = (endpoint: string, signalPath: 'logs' | 'metrics' | 'traces') => {
  const normalized = trimTrailingSlash(endpoint || DEFAULT_OTLP_ENDPOINT);
  if (normalized.endsWith(`/v1/${signalPath}`)) {
    return normalized;
  }
  if (normalized.endsWith('/v1')) {
    return `${normalized}/${signalPath}`;
  }
  return `${normalized}/v1/${signalPath}`;
};

const resolveSignalConfig = (base: BkOTConfig, signalPath: 'logs' | 'metrics' | 'traces'): SignalExporterConfig => {
  const signalConfig = base[signalPath] ?? {};
  const endpoint = signalConfig.endpoint
    ? trimTrailingSlash(signalConfig.endpoint)
    : resolveSignalEndpoint(base.endpoint, signalPath);

  // 合并而不是覆盖，让用户在公共 headers 之上对单 signal 追加/覆盖
  const mergedHeaders =
    base.headers || signalConfig.headers ? { ...(base.headers ?? {}), ...(signalConfig.headers ?? {}) } : undefined;

  return {
    endpoint,
    headers: mergedHeaders,
    concurrencyLimit: signalConfig.concurrencyLimit,
    timeoutMillis: signalConfig.timeoutMillis,
  };
};

const clampSampleRate = (sampleRate?: number) => {
  if (typeof sampleRate !== 'number' || !Number.isFinite(sampleRate)) {
    return 1;
  }
  return Math.max(0, Math.min(1, sampleRate));
};

const positiveNumber = (value: number | undefined, fallback: number) =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : fallback;

const nonNegativeNumber = (value: number | undefined, fallback: number) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : fallback;

const boundedRatio = (value: number | undefined, fallback: number) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }
  return Math.max(0, Math.min(1, value));
};

const identityRedactHttpBody = (payload: BkOTHttpBodyRedactPayload) => payload.body;

const normalizeHttpBodyConfig = (httpBody: BkOTRumConfig['httpBody']): false | Required<BkOTHttpBodyConfig> => {
  if (httpBody === false) {
    return false;
  }
  if (typeof httpBody === 'boolean') {
    return {
      maxBodySize: 10 * 1024,
      redact: identityRedactHttpBody,
    };
  }
  return {
    maxBodySize: positiveNumber(httpBody.maxBodySize, 10 * 1024),
    redact: httpBody.redact ?? identityRedactHttpBody,
  };
};

const normalizeRumConfig = (rum: BkOTConfig['rum']): NormalizedBkOTConfig['rum'] => ({
  device: rum?.device ?? true,
  httpBody: normalizeHttpBodyConfig(rum?.httpBody),
  session:
    typeof rum?.session === 'object'
      ? {
          ...rum.session,
          inactivityMs: positiveNumber(rum.session.inactivityMs, 30 * 60 * 1000),
        }
      : (rum?.session ?? true),
  pageView: rum?.pageView ?? true,
  error:
    typeof rum?.error === 'object'
      ? {
          ...rum.error,
          maxPerWindow: positiveNumber(rum.error.maxPerWindow, 5),
          windowMs: positiveNumber(rum.error.windowMs, 60_000),
        }
      : (rum?.error ?? true),
  webVitals: rum?.webVitals ?? true,
  blankScreen:
    typeof rum?.blankScreen === 'object'
      ? {
          ...rum.blankScreen,
          checkDelay: nonNegativeNumber(rum.blankScreen.checkDelay, 3000),
          threshold: boundedRatio(rum.blankScreen.threshold, 0.8),
        }
      : (rum?.blankScreen ?? true),
  websocket: rum?.websocket ?? true,
  longTask:
    typeof rum?.longTask === 'object'
      ? {
          ...rum.longTask,
          threshold: nonNegativeNumber(rum.longTask.threshold, 50),
        }
      : (rum?.longTask ?? false),
  cspViolation: rum?.cspViolation ?? false,
  routeTiming: rum?.routeTiming ?? false,
});

const identityRedactAttributes = (attributes: Attributes) => attributes;
const identityRedactUrl = (url: string) => url;

export const normalizeConfig = (config: BkOTConfig): NormalizedBkOTConfig => {
  const serviceName = config.serviceName;
  const resourceAttributes: Attributes = {
    'service.name': serviceName,
    'deployment.environment.name': config.environment ?? 'production',
    'rum.provider': 'blueking',
    'telemetry.sdk.language': 'webjs',
    ...config.resourceAttributes,
  };

  if (config.serviceVersion) {
    resourceAttributes['service.version'] = config.serviceVersion;
  }

  return {
    ...config,
    console: config.console ?? false,
    enabled: config.enabled ?? true,
    environment: config.environment ?? 'production',
    endpoint: trimTrailingSlash(config.endpoint || DEFAULT_OTLP_ENDPOINT),
    traces: resolveSignalConfig(config, 'traces'),
    metrics: resolveSignalConfig(config, 'metrics'),
    logs: resolveSignalConfig(config, 'logs'),
    ignoreUrls: config.ignoreUrls ?? [],
    propagateTraceHeaderUrls:
      config.propagateTraceHeaderUrls ?? (typeof window === 'undefined' ? [] : [window.location.origin]),
    sampleRate: clampSampleRate(config.sampleRate),
    sampleStorageKey: config.sampleStorageKey ?? `__bk_ot_sampled_${serviceName}__`,
    resourceAttributes,
    metricIntervalMillis: positiveNumber(config.metricIntervalMillis, 60000),
    instrumentations: {
      documentLoad: config.instrumentations?.documentLoad ?? true,
      fetch: config.instrumentations?.fetch ?? true,
      xhr: config.instrumentations?.xhr ?? true,
      userInteraction: config.instrumentations?.userInteraction ?? true,
    },
    rum: normalizeRumConfig(config.rum),
    plugins: config.plugins ?? [],
    autoStart: config.autoStart ?? true,
    getPageAttributes:
      config.getPageAttributes ??
      (() => ({
        'rum.page.host': typeof window === 'undefined' ? '' : window.location.host,
        'rum.page.path': typeof window === 'undefined' ? '' : window.location.pathname,
      })),
    getMetricAttributes: config.getMetricAttributes ?? (() => ({})),
    getErrorAttributes: config.getErrorAttributes ?? (() => ({})),
    getBusinessAttributes: config.getBusinessAttributes ?? (() => ({})),
    redactAttributes: config.redactAttributes ?? identityRedactAttributes,
    redactUrl: config.redactUrl ?? identityRedactUrl,
  };
};
