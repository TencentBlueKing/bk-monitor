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

import { SpanStatusCode, trace } from '@opentelemetry/api';
import { SeverityNumber } from '@opentelemetry/api-logs';

import type { BkOTRumConfig } from '../core/config';
import type { BkOTPlugin, BkOTRuntimeContext } from '../core/plugin';

const DEFAULT_WINDOW_MS = 60_000;
const DEFAULT_MAX_PER_WINDOW = 5;

const getErrorMessage = (value: unknown) => {
  if (value instanceof Error) {
    return value.message;
  }
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

const getErrorStack = (value: unknown) => (value instanceof Error ? (value.stack ?? '') : '');

// 简易 djb2 hash，足够区分常见 error 字符串组合
const hashString = (input: string): string => {
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 33) ^ input.charCodeAt(i);
  }
  return (hash >>> 0).toString(36);
};

interface ThrottleEntry {
  count: number;
  windowStart: number;
}

const createThrottle = (windowMs: number, maxPerWindow: number) => {
  const records = new Map<string, ThrottleEntry>();
  return {
    /** 返回 true 表示允许上报；false 表示触发节流被抛弃 */
    allow(key: string): boolean {
      const now = Date.now();
      const entry = records.get(key);
      if (!entry || now - entry.windowStart > windowMs) {
        records.set(key, { count: 1, windowStart: now });
        return true;
      }
      if (entry.count >= maxPerWindow) {
        return false;
      }
      entry.count += 1;
      return true;
    },
  };
};

interface EmitErrorOptions {
  context: BkOTRuntimeContext;
  error: unknown;
  exceptionType?: string;
  extra?: Record<string, unknown>;
  source: string;
  spanName: string;
  throttle: ReturnType<typeof createThrottle>;
}

const emitError = ({ context, error, exceptionType, extra = {}, source, spanName, throttle }: EmitErrorOptions) => {
  const message = getErrorMessage(error);
  const stack = getErrorStack(error);
  const throttleKey = hashString(`${source}|${message}|${stack.slice(0, 256)}`);

  if (!throttle.allow(throttleKey)) {
    return;
  }

  const activeSpan = trace.getActiveSpan();
  const exceptionLike = error instanceof Error ? error : { message, name: exceptionType ?? source };
  const attributes = {
    ...context.config.getPageAttributes(),
    ...context.config.getErrorAttributes(),
    'exception.message': message,
    'exception.stacktrace': stack,
    'exception.type': error instanceof Error ? error.name : (exceptionType ?? source),
    'bk.rum.error.source': source,
    'bk.rum.error.fingerprint': throttleKey,
    ...extra,
  };
  const errorSpan = context.startSpan(spanName, attributes);

  activeSpan?.recordException(exceptionLike);
  activeSpan?.setStatus({ code: SpanStatusCode.ERROR, message });
  errorSpan.recordException(exceptionLike);
  errorSpan.setStatus({ code: SpanStatusCode.ERROR, message });
  errorSpan.end();
  context.emitLog({
    severityNumber: SeverityNumber.ERROR,
    severityText: 'ERROR',
    body: message,
    attributes,
  });
};

export const createErrorPlugin = (option: BkOTRumConfig['error']): BkOTPlugin => {
  const listeners: Array<() => void> = [];

  return {
    name: 'error',
    enabled: Boolean(option),
    init(context) {
      if (typeof window === 'undefined') {
        return;
      }

      const windowMs = typeof option === 'object' ? (option.windowMs ?? DEFAULT_WINDOW_MS) : DEFAULT_WINDOW_MS;
      const maxPerWindow =
        typeof option === 'object' ? (option.maxPerWindow ?? DEFAULT_MAX_PER_WINDOW) : DEFAULT_MAX_PER_WINDOW;
      const throttle = createThrottle(windowMs, maxPerWindow);

      const onError = (event: ErrorEvent) => {
        emitError({
          context,
          throttle,
          spanName: 'browser.error',
          source: 'window.error',
          error: event.error ?? event.message,
          extra: {
            'code.filepath': event.filename,
            'code.lineno': event.lineno,
            'code.column': event.colno,
          },
        });
      };
      const onUnhandledRejection = (event: PromiseRejectionEvent) => {
        emitError({
          context,
          throttle,
          spanName: 'browser.unhandledrejection',
          source: 'unhandledrejection',
          error: event.reason,
          exceptionType: event.reason instanceof Error ? event.reason.name : 'UnhandledRejection',
        });
      };
      const onResourceError = (event: Event) => {
        const target = event.target as EventTarget & {
          href?: string;
          src?: string;
          tagName?: string;
        };
        if (target === window) {
          return;
        }
        const resourceUrl = target.src || target.href || '';
        emitError({
          context,
          throttle,
          spanName: 'browser.resource_error',
          source: 'resource',
          error: new Error(`Resource load failed: ${target.tagName?.toLowerCase() || 'unknown'} ${resourceUrl}`),
          exceptionType: 'ResourceError',
          extra: {
            'url.full': context.config.redactUrl(resourceUrl),
            'html.tag': target.tagName || '',
          },
        });
      };

      window.addEventListener('error', onError);
      window.addEventListener('unhandledrejection', onUnhandledRejection);
      window.addEventListener('error', onResourceError, true);
      listeners.push(
        () => window.removeEventListener('error', onError),
        () => window.removeEventListener('unhandledrejection', onUnhandledRejection),
        () => window.removeEventListener('error', onResourceError, true)
      );
    },
    shutdown() {
      while (listeners.length) {
        listeners.pop()?.();
      }
    },
  };
};
