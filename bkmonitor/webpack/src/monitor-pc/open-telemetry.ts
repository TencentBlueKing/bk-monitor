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

import { initBkOT } from '@blueking/rum';

import type { BkOTHttpBodyRedactPayload } from '@blueking/rum';

const DEFAULT_ENDPOINT = '/otel';
const DEFAULT_SERVICE_NAME = 'bk-monitor-pc';
// URL query 和 HTTP body 中可能携带敏感参数，默认脱敏。
const SENSITIVE_QUERY_KEYS = [
  'token',
  'access_token',
  'refresh_token',
  'password',
  'pwd',
  'secret',
  'auth',
  'session',
  'sessionid',
];

const getUrlParam = (key: string) => {
  try {
    return new URLSearchParams(window.location.search).get(key) || '';
  } catch {
    return '';
  }
};

const getBkRuntimeAttributes = () => ({
  'bk.biz.id': String(window.bk_biz_id || getUrlParam('bizId') || ''),
  'bk.space.uid': String(window.space_uid || getUrlParam('space_uid') || ''),
  'bk.tenant.id': window.bk_tenant_id || '',
});

// 默认 URL 脱敏：替换敏感 query 参数值为 [REDACTED]
const defaultRedactUrl = (url: string): string => {
  if (!url) return url;
  try {
    const parsed = new URL(url, window.location.origin);
    let mutated = false;
    for (const key of Array.from(parsed.searchParams.keys())) {
      if (SENSITIVE_QUERY_KEYS.includes(key.toLowerCase())) {
        parsed.searchParams.set(key, '[REDACTED]');
        mutated = true;
      }
    }
    return mutated ? parsed.toString() : url;
  } catch {
    return url;
  }
};

const redactSensitiveJsonValue = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map(redactSensitiveJsonValue);
  }
  if (!value || typeof value !== 'object') {
    return value;
  }
  return Object.entries(value as Record<string, unknown>).reduce<Record<string, unknown>>((result, [key, item]) => {
    result[key] = SENSITIVE_QUERY_KEYS.includes(key.toLowerCase()) ? '[REDACTED]' : redactSensitiveJsonValue(item);
    return result;
  }, {});
};

// 请求体/响应体由使用方配置脱敏策略，这里提供监控 PC 默认策略。
const defaultRedactHttpBody = ({ body, contentType }: BkOTHttpBodyRedactPayload) => {
  if (!body) {
    return body;
  }
  try {
    if (contentType?.includes('application/json')) {
      return JSON.stringify(redactSensitiveJsonValue(JSON.parse(body)));
    }
    if (contentType?.includes('application/x-www-form-urlencoded')) {
      const params = new URLSearchParams(body);
      for (const key of Array.from(params.keys())) {
        if (SENSITIVE_QUERY_KEYS.includes(key.toLowerCase())) {
          params.set(key, '[REDACTED]');
        }
      }
      return params.toString();
    }
  } catch {
    return body;
  }
  return body;
};

try {
  initBkOT({
    console: process.env.NODE_ENV === 'development',
    enabled: true,
    environment: process.env.NODE_ENV,
    getBusinessAttributes: getBkRuntimeAttributes,
    getErrorAttributes: getBkRuntimeAttributes,
    getMetricAttributes: getBkRuntimeAttributes,
    endpoint: DEFAULT_ENDPOINT,
    ignoreUrls: [/\/sockjs-node/, /\/__webpack_hmr/],
    propagateTraceHeaderUrls: [window.location.origin],
    redactUrl: defaultRedactUrl,
    resourceAttributes: getBkRuntimeAttributes(),
    sampleRate: 1,
    serviceName: DEFAULT_SERVICE_NAME,
    serviceVersion: '0.0.0',
    rum: {
      httpBody: {
        maxBodySize: 20 * 1024,
        redact: defaultRedactHttpBody,
      },
      routeTiming: true,
      websocket: true,
      longTask: {
        threshold: 50,
      },
      cspViolation: true,
      blankScreen: true,
      error: true,
      webVitals: true,
    },
  });
} catch (err) {
  // RUM 初始化失败不影响主业务运行
  globalThis.console?.warn('[bk-monitor-pc][open-telemetry] init failed:', err);
}
