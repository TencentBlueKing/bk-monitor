/* eslint-disable @typescript-eslint/naming-convention */
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

import { type Instrumentation, registerInstrumentations } from '@opentelemetry/instrumentation';

import { shouldIgnoreUrl, shouldPropagateTraceHeader } from '../core/url';

import type { BkOTInstrumentationsConfig } from '../core/config';
import type { BkOTPlugin, BkOTRuntimeContext } from '../core/plugin';

const URL_KEYS = ['http.url', 'url.full'];

// OTel 官方 instrumentation 内部对每个 URL 调用 matcher.test(url)，
// 这里把"用户函数 + 自身 endpoint 过滤"包装成具备 .test 的对象，是与 OTel 一致的扩展用法
const toUrlPredicateMatcher = (predicate: (url: string) => boolean): RegExp =>
  ({ test: predicate }) as unknown as RegExp;

// 对官方 instrumentation 创建的 span，统一附加 page attributes 与 URL 脱敏
const decorateSpan = (
  context: BkOTRuntimeContext,
  span: {
    attributes?: Record<string, any>;
    setAttribute: (key: string, value: any) => void;
    setAttributes: (attrs: Record<string, any>) => void;
  }
) => {
  span.setAttributes(context.applyRedact(context.config.getPageAttributes()));
  for (const key of URL_KEYS) {
    const value = span.attributes?.[key];
    if (typeof value === 'string') {
      const redactedAttributes = context.applyRedact({ [key]: context.config.redactUrl(value) });
      const redactedUrl = redactedAttributes[key];
      if (typeof redactedUrl === 'string') {
        span.setAttribute(key, redactedUrl);
      }
    }
  }
};

export const createCommonInstrumentationsPlugin = (option: BkOTInstrumentationsConfig): BkOTPlugin => {
  const instrumentations: Instrumentation[] = [];

  return {
    name: 'official-instrumentations',
    enabled: Boolean(option.documentLoad || option.fetch || option.xhr || option.userInteraction),
    async init(context) {
      const loadedInstrumentations: Instrumentation[] = [];
      const ignoreUrls = [toUrlPredicateMatcher(url => shouldIgnoreUrl(context.config, url))];
      const propagateTraceHeaderCorsUrls = [
        toUrlPredicateMatcher(url => shouldPropagateTraceHeader(context.config, url)),
      ];

      if (option.documentLoad) {
        const { DocumentLoadInstrumentation } = await import('@opentelemetry/instrumentation-document-load');
        loadedInstrumentations.push(
          new DocumentLoadInstrumentation({
            semconvStabilityOptIn: 'http',
          })
        );
      }

      if (option.fetch) {
        const { FetchInstrumentation } = await import('@opentelemetry/instrumentation-fetch');
        loadedInstrumentations.push(
          new FetchInstrumentation({
            applyCustomAttributesOnSpan: span => decorateSpan(context, span as any),
            ignoreUrls,
            propagateTraceHeaderCorsUrls,
            semconvStabilityOptIn: 'http',
            ignoreNetworkEvents: false,
          })
        );
      }

      if (option.xhr) {
        const { XMLHttpRequestInstrumentation } = await import('@opentelemetry/instrumentation-xml-http-request');
        loadedInstrumentations.push(
          new XMLHttpRequestInstrumentation({
            applyCustomAttributesOnSpan: span => decorateSpan(context, span as any),
            ignoreUrls,
            propagateTraceHeaderCorsUrls,
            semconvStabilityOptIn: 'http',
            ignoreNetworkEvents: false,
          })
        );
      }

      if (option.userInteraction) {
        const { UserInteractionInstrumentation } = await import('@opentelemetry/instrumentation-user-interaction');
        const userInteractionConfig =
          typeof option.userInteraction === 'object'
            ? { eventNames: option.userInteraction.eventNames as Array<keyof HTMLElementEventMap> }
            : undefined;
        loadedInstrumentations.push(new UserInteractionInstrumentation(userInteractionConfig));
      }

      instrumentations.push(...loadedInstrumentations);
      registerInstrumentations({ instrumentations: loadedInstrumentations });
    },
    shutdown() {
      while (instrumentations.length) {
        instrumentations.pop()?.disable?.();
      }
    },
  };
};
