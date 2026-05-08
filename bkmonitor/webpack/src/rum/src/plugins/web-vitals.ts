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
import type { Attributes } from '@opentelemetry/api';

interface VitalLike {
  attribution?: Record<string, unknown>;
  id?: string;
  name: string;
  rating?: string;
  value: number;
}

const getNavigationType = () => {
  const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;

  return navigation?.type || 'unknown';
};

// 仅挑选低基数、可枚举的字段进 metric attributes，避免指标维度爆炸
const getMetricDimensions = (metric: VitalLike): Attributes => ({
  'rum.navigation.type': getNavigationType(),
  'web_vital.name': metric.name,
  'web_vital.rating': metric.rating,
});

// 把 attribution 中价值最高的字段抽出来（仅放进 span/log，不放进 metric）
const pickAttribution = (metric: VitalLike, redactUrl: (url: string) => string): Attributes => {
  const attr = metric.attribution ?? {};
  const result: Attributes = {};

  const setIfDefined = (key: string, value: unknown, transform?: (value: string) => string) => {
    if (value === undefined || value === null) return;
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      result[key] = typeof value === 'string' && transform ? transform(value) : value;
    }
  };

  switch (metric.name) {
    case 'LCP':
      setIfDefined('web_vital.lcp.url', attr.url, redactUrl);
      setIfDefined('web_vital.lcp.target', attr.target);
      setIfDefined('web_vital.lcp.element_render_delay', attr.elementRenderDelay);
      setIfDefined('web_vital.lcp.resource_load_duration', attr.resourceLoadDuration);
      setIfDefined('web_vital.lcp.time_to_first_byte', attr.timeToFirstByte);
      break;
    case 'CLS':
      setIfDefined('web_vital.cls.largest_shift_target', attr.largestShiftTarget);
      setIfDefined('web_vital.cls.largest_shift_value', attr.largestShiftValue);
      setIfDefined('web_vital.cls.load_state', attr.loadState);
      break;
    case 'INP':
      setIfDefined('web_vital.inp.interaction_target', attr.interactionTarget);
      setIfDefined('web_vital.inp.interaction_type', attr.interactionType);
      setIfDefined('web_vital.inp.input_delay', attr.inputDelay);
      setIfDefined('web_vital.inp.processing_duration', attr.processingDuration);
      setIfDefined('web_vital.inp.presentation_delay', attr.presentationDelay);
      break;
    case 'FCP':
      setIfDefined('web_vital.fcp.time_to_first_byte', attr.timeToFirstByte);
      setIfDefined('web_vital.fcp.load_state', attr.loadState);
      break;
    case 'TTFB':
      setIfDefined('web_vital.ttfb.waiting_duration', attr.waitingDuration);
      setIfDefined('web_vital.ttfb.dns_duration', attr.dnsDuration);
      setIfDefined('web_vital.ttfb.connection_duration', attr.connectionDuration);
      setIfDefined('web_vital.ttfb.request_duration', attr.requestDuration);
      break;
    default:
      break;
  }
  return result;
};

export const createWebVitalsPlugin = (enabled: BkOTRumConfig['webVitals']): BkOTPlugin => ({
  name: 'web-vitals',
  enabled: Boolean(enabled),
  async init(context) {
    if (typeof window === 'undefined') {
      return;
    }

    const { onCLS, onFCP, onINP, onLCP, onTTFB } = await import('web-vitals/attribution');
    const clsHistogram = context.meter.createHistogram('browser.web_vital.cls', {
      unit: '1',
      description: 'Cumulative Layout Shift',
    });
    const durationHistogram = context.meter.createHistogram('browser.web_vital.duration', {
      unit: 'ms',
      description: 'Web Vitals duration metrics, including FCP, INP, LCP and TTFB',
    });

    const recordSpan = (metric: VitalLike) => {
      const span = context.startSpan('browser.web_vital', {
        ...context.config.getPageAttributes(),
        ...context.config.getMetricAttributes(),
        ...getMetricDimensions(metric),
        // 单条度量唯一 ID 仅放进 span，避免污染 metric 维度
        'web_vital.id': metric.id,
        'web_vital.value': metric.value,
        ...pickAttribution(metric, context.config.redactUrl),
      });
      span.end();
    };

    const recordDurationMetric = (metric: VitalLike) => {
      durationHistogram.record(
        metric.value,
        context.applyRedact({
          ...context.config.getPageAttributes(),
          ...context.config.getMetricAttributes(),
          ...getMetricDimensions(metric),
        })
      );
      recordSpan(metric);
    };

    onCLS(metric => {
      clsHistogram.record(
        metric.value,
        context.applyRedact({
          ...context.config.getPageAttributes(),
          ...context.config.getMetricAttributes(),
          ...getMetricDimensions(metric),
        })
      );
      recordSpan(metric);
    });
    onFCP(recordDurationMetric);
    onINP(recordDurationMetric);
    onLCP(recordDurationMetric);
    onTTFB(recordDurationMetric);
  },
});
