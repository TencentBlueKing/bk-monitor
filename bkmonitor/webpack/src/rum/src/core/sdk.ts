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

import {
  type Attributes,
  type Span,
  context,
  metrics,
  propagation,
  SpanKind,
  SpanStatusCode,
  trace,
} from '@opentelemetry/api';
import { logs } from '@opentelemetry/api-logs';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { W3CTraceContextPropagator } from '@opentelemetry/core';
import { OTLPLogExporter } from '@opentelemetry/exporter-logs-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { BatchLogRecordProcessor, LoggerProvider } from '@opentelemetry/sdk-logs';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { BatchSpanProcessor, ParentBasedSampler, TraceIdRatioBasedSampler } from '@opentelemetry/sdk-trace-base';
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';

import { createBlankScreenPlugin } from '../plugins/blank-screen';
import { createCommonInstrumentationsPlugin } from '../plugins/common';
import { createCspViolationPlugin } from '../plugins/csp-violation';
import { createDevicePlugin } from '../plugins/device';
import { createErrorPlugin } from '../plugins/error';
import { createHttpBodyPlugin } from '../plugins/http-body';
import { createLongTaskPlugin } from '../plugins/long-task';
import { createPageViewPlugin } from '../plugins/page-view';
import { createRouteTimingPlugin } from '../plugins/route-timing';
import { createSessionPlugin } from '../plugins/session';
import { createWebVitalsPlugin } from '../plugins/web-vitals';
import { createWebSocketPlugin } from '../plugins/websocket';
import { type BkOTBusinessEventPayload, type BkOTConfig, type NormalizedBkOTConfig, normalizeConfig } from './config';
import { type BkOTPlugin, type BkOTRuntimeContext, PluginManager } from './plugin';
import { FilteringSpanProcessor } from './processor';
import { isBkOTSampled } from './sampling';

import type { LogRecord } from '@opentelemetry/api-logs';

export interface BkOTInstance extends BkOTRuntimeContext {
  flush: () => Promise<void>;
  reportBusinessEvent: (payload: BkOTBusinessEventPayload) => void;
  shutdown: () => Promise<void>;
  start: () => Promise<void>;
}

const createExporterOptions = (config: NormalizedBkOTConfig['traces']) => ({
  url: config.endpoint,
  headers: config.headers,
  concurrencyLimit: config.concurrencyLimit,
  timeoutMillis: config.timeoutMillis,
});

type ConsoleSignal = 'logs' | 'metrics' | 'traces';

/**
 * 用 Proxy 包装一层 console 旁路，避免直接 mutate 第三方 exporter 实例（其内部可能含 #private fields）。
 */
const wrapWithConsole = <TExporter extends { export: (...args: any[]) => any }>(
  exporter: TExporter,
  signal: ConsoleSignal,
  enabled: boolean
): TExporter => {
  if (!enabled) {
    return exporter;
  }
  return new Proxy(exporter, {
    get(target, prop, receiver) {
      if (prop === 'export') {
        return (records: unknown, callback: unknown) => {
          globalThis.console?.log(`[bk-ot][${signal}]`, records);
          return (target as { export: (...args: unknown[]) => unknown }).export(records, callback);
        };
      }
      const value = Reflect.get(target, prop, receiver);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });
};

// 负责给原生 fetch/xhr 注入 W3C traceparent 头；仅 SDK 启用时装载，避免 disabled 状态仍 patch 全局 API
const getCorePlugins = (config: NormalizedBkOTConfig): BkOTPlugin[] => [
  createCommonInstrumentationsPlugin(config.instrumentations),
];

// 仅在采样命中时启用的"会主动产生数据"的 RUM 插件
const getRumPlugins = (config: NormalizedBkOTConfig): BkOTPlugin[] => [
  createDevicePlugin(config.rum.device),
  createHttpBodyPlugin(config.rum.httpBody),
  createSessionPlugin(config.rum.session),
  createPageViewPlugin(config.rum.pageView),
  createErrorPlugin(config.rum.error),
  createWebVitalsPlugin(config.rum.webVitals),
  createBlankScreenPlugin(config.rum.blankScreen),
  createWebSocketPlugin(config.rum.websocket),
  createLongTaskPlugin(config.rum.longTask),
  createCspViolationPlugin(config.rum.cspViolation),
  createRouteTimingPlugin(config.rum.routeTiming),
];

type SdkLifecyclePhase = 'idle' | 'started' | 'stopped';

export const createBkOT = (inputConfig: BkOTConfig): BkOTInstance => {
  const config = normalizeConfig(inputConfig);
  const sampled = config.enabled && isBkOTSampled(config);
  const resource = resourceFromAttributes(config.resourceAttributes);
  const spanExporter = wrapWithConsole(
    new OTLPTraceExporter(createExporterOptions(config.traces)),
    'traces',
    config.console
  );
  const metricExporter = wrapWithConsole(
    new OTLPMetricExporter(createExporterOptions(config.metrics)),
    'metrics',
    config.console
  );
  const logExporter = wrapWithConsole(new OTLPLogExporter(createExporterOptions(config.logs)), 'logs', config.console);
  const batchSpanProcessor = new BatchSpanProcessor(spanExporter, config.spanBatch);
  const spanProcessor = new FilteringSpanProcessor(batchSpanProcessor, config);
  const metricReader = new PeriodicExportingMetricReader({
    exporter: metricExporter,
    exportIntervalMillis: config.metricIntervalMillis,
  });
  const logProcessor = new BatchLogRecordProcessor(logExporter);
  const tracerProvider = new WebTracerProvider({
    resource,
    sampler: new ParentBasedSampler({
      root: new TraceIdRatioBasedSampler(sampled ? 1 : 0),
    }),
    spanProcessors: [spanProcessor],
  });
  const meterProvider = new MeterProvider({
    resource,
    readers: [metricReader],
  });
  const loggerProvider = new LoggerProvider({
    resource,
    processors: [logProcessor],
  });
  const tracer = tracerProvider.getTracer(config.serviceName, config.serviceVersion);
  const meter = meterProvider.getMeter(config.serviceName, config.serviceVersion);
  const logger = loggerProvider.getLogger(config.serviceName, config.serviceVersion);
  const runtimeAttributes: Attributes = {
    'bk.rum.sampled': sampled,
  };
  // 核心插件在 SDK 启用时装载；RUM 数据上报类插件仅在采样命中时装载
  const pluginManager = new PluginManager([
    ...(config.enabled ? getCorePlugins(config) : []),
    ...(sampled ? [...getRumPlugins(config), ...config.plugins] : []),
  ]);
  const teardownCallbacks: Array<() => void> = [];
  let phase: SdkLifecyclePhase = 'idle';

  const getRuntimeAttributes = () => ({ ...runtimeAttributes });
  const setRuntimeAttributes = (attributes: Attributes) => {
    Object.assign(runtimeAttributes, attributes);
  };
  const applyRedact = (attributes: Attributes) => config.redactAttributes(attributes);
  const startSpan = (name: string, attributes: Attributes = {}): Span =>
    tracer.startSpan(name, {
      kind: SpanKind.INTERNAL,
      attributes: applyRedact({
        ...getRuntimeAttributes(),
        ...attributes,
      }),
    });
  const emitLog = (record: LogRecord) => {
    const merged: LogRecord = {
      ...record,
      attributes: applyRedact({
        ...getRuntimeAttributes(),
        ...((record.attributes ?? {}) as Attributes),
      }),
    };
    logger.emit(merged);
  };

  const instance: BkOTInstance = {
    config,
    tracer,
    meter,
    logger,
    applyRedact,
    emitLog,
    getRuntimeAttributes,
    setRuntimeAttributes,
    startSpan,
    reportBusinessEvent({ attributes = {}, error, name }) {
      if (!sampled) {
        // 未采样时静默丢弃；如需调试请把 console 选项打开
        if (config.console) {
          globalThis.console?.warn('[bk-ot] business event dropped (not sampled):', name);
        }
        return;
      }

      const span = startSpan(`business.${name}`, {
        ...config.getPageAttributes(),
        ...config.getBusinessAttributes(),
        ...attributes,
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
    },
    async start() {
      if (phase === 'started') {
        return;
      }
      if (phase === 'stopped') {
        // shutdown 已经销毁了 provider/processor，此处禁止再次启动
        throw new Error('[bk-ot] instance has been shut down and cannot be restarted; create a new instance instead.');
      }
      if (!config.enabled) {
        phase = 'started';
        return;
      }
      propagation.setGlobalPropagator(new W3CTraceContextPropagator());
      tracerProvider.register({
        contextManager: new ZoneContextManager(),
      });
      metrics.setGlobalMeterProvider(meterProvider);
      logs.setGlobalLoggerProvider(loggerProvider);
      try {
        await pluginManager.start(instance);
        if (typeof window !== 'undefined' && typeof document !== 'undefined') {
          const flushOnPageHide = () => {
            void instance.flush();
          };
          const flushOnHidden = () => {
            if (document.visibilityState === 'hidden') {
              void instance.flush();
            }
          };
          window.addEventListener('pagehide', flushOnPageHide);
          document.addEventListener('visibilitychange', flushOnHidden);
          teardownCallbacks.push(
            () => window.removeEventListener('pagehide', flushOnPageHide),
            () => document.removeEventListener('visibilitychange', flushOnHidden)
          );
        }
      } catch (error) {
        while (teardownCallbacks.length) {
          teardownCallbacks.pop()?.();
        }
        await pluginManager.shutdown();
        trace.disable();
        metrics.disable();
        context.disable();
        throw error;
      }
      phase = 'started';
    },
    async flush() {
      await pluginManager.flush();
      await tracerProvider.forceFlush();
      await meterProvider.forceFlush();
      await loggerProvider.forceFlush();
    },
    async shutdown() {
      if (phase === 'stopped') {
        return;
      }
      await instance.flush();
      while (teardownCallbacks.length) {
        teardownCallbacks.pop()?.();
      }
      await pluginManager.shutdown();
      await tracerProvider.shutdown();
      await meterProvider.shutdown();
      await loggerProvider.shutdown();
      trace.disable();
      metrics.disable();
      context.disable();
      phase = 'stopped';
    },
  };

  if (config.autoStart) {
    void instance.start().catch(error => {
      globalThis.console?.warn('[bk-ot] auto start failed:', error);
    });
  }

  return instance;
};

export const initBkOT = createBkOT;
