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

import { SeverityNumber } from '@opentelemetry/api-logs';

import type { BkOTRumConfig } from '../core/config';
import type { BkOTPlugin } from '../core/plugin';

const DEFAULT_SELECTOR = 'body';
const DEFAULT_CHECK_DELAY = 3000;
const DEFAULT_THRESHOLD = 0.8;
// 常见 loading mask / spinner 选择器，命中说明页面正在加载而非空白
const DEFAULT_LOADING_SELECTORS = [
  '[data-loading="true"]',
  '[aria-busy="true"]',
  '.loading',
  '.is-loading',
  '.spinner',
  '.skeleton',
  '.bk-loading',
];

const SAMPLE_POINTS: Array<[number, number]> = [
  [0.5, 0.5],
  [0.25, 0.25],
  [0.75, 0.25],
  [0.25, 0.75],
  [0.75, 0.75],
];

const getElementSelector = (element: Element | null) => {
  if (!element) {
    return '';
  }
  const tag = element.tagName.toLowerCase();
  if (element.id) {
    return `${tag}#${element.id}`;
  }
  return tag;
};

const matchesAny = (element: Element | null, selectors: string[]) => {
  if (!element) return false;
  return selectors.some(selector => {
    try {
      return element.matches(selector) || !!element.closest(selector);
    } catch {
      return false;
    }
  });
};

// 页面就绪后再开始计时，避免 SPA / 慢加载场景下检测时机过早
const whenDocumentReady = (callback: () => void) => {
  if (typeof document === 'undefined') return;
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    callback();
    return;
  }
  const handler = () => {
    document.removeEventListener('DOMContentLoaded', handler);
    callback();
  };
  document.addEventListener('DOMContentLoaded', handler);
};

export const createBlankScreenPlugin = (option: BkOTRumConfig['blankScreen']): BkOTPlugin => {
  let timer: number | undefined;

  return {
    name: 'blank-screen',
    enabled: Boolean(option),
    init(context) {
      if (typeof window === 'undefined' || typeof document === 'undefined') {
        return;
      }

      const optionObj = typeof option === 'object' ? option : {};
      const rootSelector = optionObj.rootSelector ?? DEFAULT_SELECTOR;
      const checkDelay = optionObj.checkDelay ?? DEFAULT_CHECK_DELAY;
      const threshold = optionObj.threshold ?? DEFAULT_THRESHOLD;
      const loadingSelectors = [...DEFAULT_LOADING_SELECTORS, ...(optionObj.ignoreSelectors ?? [])];

      // 仅创建一次 counter，避免每次回调都触发一次 meter lookup
      const counter = context.meter.createCounter('browser.blank_screen.count', {
        description: 'Number of suspected blank screen detections',
      });

      whenDocumentReady(() => {
        timer = window.setTimeout(() => {
          const root = document.querySelector(rootSelector);
          let emptyCount = 0;
          let loadingCount = 0;

          for (const [x, y] of SAMPLE_POINTS) {
            const element = document.elementFromPoint(window.innerWidth * x, window.innerHeight * y);
            if (matchesAny(element, loadingSelectors)) {
              loadingCount += 1;
              continue;
            }
            if (element === root || element === document.body || element === document.documentElement) {
              emptyCount += 1;
            }
          }

          const score = emptyCount / SAMPLE_POINTS.length;
          // 触发 loading mask 的样本算"非空"，但若全部点都是 loading，则视为待定不上报
          if (loadingCount === SAMPLE_POINTS.length) {
            return;
          }
          const isBlank = score >= threshold;
          const attributes = {
            'bk.rum.blank_screen.score': score,
            'bk.rum.blank_screen.threshold': threshold,
            'bk.rum.blank_screen.root': rootSelector,
            'bk.rum.blank_screen.detected': isBlank,
            'bk.rum.blank_screen.center_element': getElementSelector(
              document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2)
            ),
            'bk.rum.blank_screen.dom_node_count': document.body?.getElementsByTagName('*').length ?? 0,
          };

          if (isBlank) {
            counter.add(
              1,
              context.applyRedact({
                // 仅放进低基数维度，center_element 等高基数字段只走 log
                'bk.rum.blank_screen.root': rootSelector,
              })
            );
            context.emitLog({
              severityNumber: SeverityNumber.ERROR,
              severityText: 'ERROR',
              body: 'browser.blank_screen',
              attributes,
            });
          }
        }, checkDelay);
      });
    },
    shutdown() {
      if (timer !== undefined && typeof window !== 'undefined') {
        window.clearTimeout(timer);
      }
    },
  };
};
