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

import { subscribeRouteChange } from './route-observer';

import type { BkOTRumConfig } from '../core/config';
import type { BkOTPlugin } from '../core/plugin';

const getCurrentUrl = () => {
  if (typeof location === 'undefined') {
    return '';
  }
  return location.href;
};

export const createPageViewPlugin = (enabled: BkOTRumConfig['pageView']): BkOTPlugin => {
  const teardownCallbacks: Array<() => void> = [];

  return {
    name: 'page-view',
    enabled: Boolean(enabled),
    init(context) {
      if (typeof window === 'undefined') {
        return;
      }

      // 同 URL 去重：路由库常常因 query/hash 微调反复 push 同一 URL，去重避免重复上报
      let lastUrl = '';

      const emitPageView = (source: string, previousUrl = lastUrl) => {
        const currentUrl = getCurrentUrl();
        if (currentUrl === lastUrl) {
          return;
        }
        lastUrl = currentUrl;

        const span = context.startSpan('browser.page_view', {
          ...context.config.getPageAttributes(),
          'url.full': context.config.redactUrl(currentUrl),
          'url.previous': context.config.redactUrl(previousUrl),
          'document.referrer': context.config.redactUrl(document.referrer || ''),
          'bk.rum.event.source': source,
        });
        span.end();
      };

      const unsubscribe = subscribeRouteChange(event => {
        emitPageView(event.source, event.fromUrl);
      });
      emitPageView('load');

      teardownCallbacks.push(unsubscribe);
    },
    shutdown() {
      while (teardownCallbacks.length) {
        teardownCallbacks.pop()?.();
      }
    },
  };
};
