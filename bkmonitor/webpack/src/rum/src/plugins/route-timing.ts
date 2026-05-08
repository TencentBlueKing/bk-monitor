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

/**
 * 估算 SPA 路由切换耗时：路由变更 → 双 raf + 一个宏任务后视为"渲染完成"。
 * 不依赖具体框架，但仅是粗粒度估算；如需精确，业务可走自定义 plugin 在框架钩子内 startSpan/end。
 */
export const createRouteTimingPlugin = (enabled: BkOTRumConfig['routeTiming']): BkOTPlugin => {
  const teardownCallbacks: Array<() => void> = [];

  return {
    name: 'route-timing',
    enabled: Boolean(enabled),
    init(context) {
      if (typeof window === 'undefined' || typeof history === 'undefined') {
        return;
      }

      const histogram = context.meter.createHistogram('browser.route_change.duration', {
        unit: 'ms',
        description: 'Estimated SPA route change duration (route start to next idle)',
      });

      const measure = (source: string, fromUrl: string, toUrl: string) => {
        const startedAt = performance.now();
        const finalize = () => {
          const duration = performance.now() - startedAt;
          const dimensions = context.applyRedact({
            ...context.config.getPageAttributes(),
            ...context.config.getMetricAttributes(),
            'route.change.source': source,
          });
          histogram.record(duration, dimensions);
          const span = context.startSpan('browser.route_change', {
            ...dimensions,
            'url.full': context.config.redactUrl(toUrl),
            'url.previous': context.config.redactUrl(fromUrl),
            'route.change.duration_ms': duration,
          });
          span.end();
        };
        // 双 raf 等到下一帧渲染后，再补一个宏任务，覆盖大多数同步组件挂载场景
        requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(finalize, 0)));
      };

      const unsubscribe = subscribeRouteChange(event => {
        if (event.fromUrl === event.toUrl) {
          return;
        }
        measure(event.source, event.fromUrl, event.toUrl);
      });

      teardownCallbacks.push(unsubscribe);
    },
    shutdown() {
      while (teardownCallbacks.length) {
        teardownCallbacks.pop()?.();
      }
    },
  };
};
