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

import type { NormalizedBkOTConfig, UrlMatcher } from './config';

const getBaseUrl = () => (typeof window === 'undefined' ? 'http://localhost' : window.location.origin);

const toAbsoluteUrl = (url: string) => {
  try {
    return new URL(url, getBaseUrl()).href;
  } catch {
    return url;
  }
};

// 去掉 trailing slash，便于 path 边界对齐比较
const stripTrailingSlash = (value: string) => (value.length > 1 ? value.replace(/\/+$/, '') : value);

const matchUrlString = (matcher: string, target: string) => {
  const normalizedMatcher = stripTrailingSlash(toAbsoluteUrl(matcher));
  const normalizedTarget = stripTrailingSlash(target);

  if (normalizedTarget === normalizedMatcher) {
    return true;
  }

  // 边界匹配：必须在 path 段、query 或 fragment 边界处衔接，避免 /api 误命中 /api2
  const boundaryStart = `${normalizedMatcher}/`;
  if (normalizedTarget.startsWith(boundaryStart)) {
    return true;
  }
  if (normalizedTarget.startsWith(`${normalizedMatcher}?`)) {
    return true;
  }
  return normalizedTarget.startsWith(`${normalizedMatcher}#`);
};

export const matchUrl = (matcher: UrlMatcher, url: string) => {
  if (typeof matcher === 'function') {
    return matcher(url);
  }

  const targetUrl = toAbsoluteUrl(url);
  if (typeof matcher === 'string') {
    return matchUrlString(matcher, targetUrl);
  }

  return matcher.test(targetUrl);
};

// 比较两个 URL 是否指向同一资源（忽略 query/fragment 与末尾斜杠）
const isSameResource = (left: string, right: string) => {
  const stripped = (value: string) => stripTrailingSlash(value.replace(/[?#].*$/, ''));
  return stripped(left) === stripped(right);
};

export const isBkOTEndpoint = (config: NormalizedBkOTConfig, url: string) => {
  const targetUrl = toAbsoluteUrl(url);

  return [config.traces.endpoint, config.metrics.endpoint, config.logs.endpoint].some(endpoint =>
    isSameResource(targetUrl, toAbsoluteUrl(endpoint))
  );
};

export const shouldIgnoreUrl = (config: NormalizedBkOTConfig, url: string) =>
  isBkOTEndpoint(config, url) || config.ignoreUrls.some(pattern => matchUrl(pattern, url));

export const shouldPropagateTraceHeader = (config: NormalizedBkOTConfig, url: string) =>
  config.propagateTraceHeaderUrls.some(pattern => matchUrl(pattern, url));
