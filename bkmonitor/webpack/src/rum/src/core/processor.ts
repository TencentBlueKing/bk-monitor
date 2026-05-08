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

import { isBkOTEndpoint } from './url';

import type { NormalizedBkOTConfig } from './config';
import type { Context } from '@opentelemetry/api';
import type { ReadableSpan, Span, SpanProcessor } from '@opentelemetry/sdk-trace-base';

const SELF_TELEMETRY_URL_KEYS = ['http.url', 'url.full'];

const getSpanUrl = (span: ReadableSpan): string | undefined => {
  for (const key of SELF_TELEMETRY_URL_KEYS) {
    const value = span.attributes?.[key];
    if (typeof value === 'string') {
      return value;
    }
  }
  return undefined;
};

/**
 * 包装 SpanProcessor，在 onEnd 阶段过滤指向自身上报 endpoint 的 span，
 * 兜底防止 official fetch/xhr 拦截器对 OTel 自身请求产生回环 span。
 */
export class FilteringSpanProcessor implements SpanProcessor {
  public constructor(
    private readonly inner: SpanProcessor,
    private readonly config: NormalizedBkOTConfig
  ) {}

  public forceFlush(): Promise<void> {
    return this.inner.forceFlush();
  }

  public onEnd(span: ReadableSpan): void {
    const url = getSpanUrl(span);
    if (url && isBkOTEndpoint(this.config, url)) {
      return;
    }
    this.inner.onEnd(span);
  }

  public onStart(span: Span, parentContext: Context): void {
    this.inner.onStart(span, parentContext);
  }

  public shutdown(): Promise<void> {
    return this.inner.shutdown();
  }
}
