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

import type { BkOTRumConfig } from '../core/config';
import type { BkOTPlugin } from '../core/plugin';

const DEFAULT_THRESHOLD_MS = 50;

interface LongTaskAttribution {
  containerId?: string;
  containerName?: string;
  containerSrc?: string;
  containerType?: string;
  name?: string;
}

interface LongTaskEntry extends PerformanceEntry {
  attribution?: LongTaskAttribution[];
}

/**
 * Long Task 监控：通过 PerformanceObserver type=longtask 捕获 >= threshold 的主线程长任务。
 * 默认关闭，建议在性能敏感模块按需开启。
 */
export const createLongTaskPlugin = (option: BkOTRumConfig['longTask']): BkOTPlugin => {
  let observer: PerformanceObserver | undefined;

  return {
    name: 'long-task',
    enabled: Boolean(option),
    init(context) {
      if (typeof PerformanceObserver === 'undefined') {
        return;
      }
      const entryTypes = (PerformanceObserver as unknown as { supportedEntryTypes?: string[] }).supportedEntryTypes;
      if (!entryTypes?.includes('longtask')) {
        return;
      }

      const threshold = typeof option === 'object' ? (option.threshold ?? DEFAULT_THRESHOLD_MS) : DEFAULT_THRESHOLD_MS;
      const counter = context.meter.createCounter('browser.long_task.count', {
        description: 'Number of long tasks observed (duration >= threshold)',
      });
      const durationHistogram = context.meter.createHistogram('browser.long_task.duration', {
        unit: 'ms',
        description: 'Duration of long tasks',
      });

      try {
        observer = new PerformanceObserver(list => {
          for (const entry of list.getEntries() as LongTaskEntry[]) {
            if (entry.duration < threshold) {
              continue;
            }
            const attribution = entry.attribution?.[0];
            const dimensions = context.applyRedact({
              ...context.config.getPageAttributes(),
              ...context.config.getMetricAttributes(),
              'long_task.name': entry.name,
              'long_task.attribution': attribution?.name ?? 'unknown',
            });
            counter.add(1, dimensions);
            durationHistogram.record(entry.duration, dimensions);
          }
        });
        observer.observe({ type: 'longtask', buffered: true });
      } catch {
        observer = undefined;
      }
    },
    shutdown() {
      observer?.disconnect();
      observer = undefined;
    },
  };
};
