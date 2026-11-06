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
import { Component, Inject, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import TraceExplore from './trace-explore';

import type { IViewOptions } from '../../typings';
import type { TimeRangeType } from 'trace/components/time-range/utils';

import './index.scss';

function parseRouteJson<T>(val: unknown, fallback: T): T {
  if (val == null || val === '') return fallback;
  if (Array.isArray(val) || (typeof val === 'object' && val !== null)) return val as T;
  if (typeof val !== 'string') return fallback;
  try {
    return JSON.parse(val) as T;
  } catch {
    try {
      return JSON.parse(decodeURIComponent(val)) as T;
    } catch {
      return fallback;
    }
  }
}

function stringifyRouteJson(val: unknown) {
  // 只序列化；编码交给 vue-router。再 encodeURIComponent 会和 $route.query 对不上，触发 CommonPage 换 key 死循环。
  return JSON.stringify(val ?? []);
}

function routeJsonUnchanged(current: unknown, nextVal: unknown) {
  return JSON.stringify(parseRouteJson(current, [])) === JSON.stringify(nextVal ?? []);
}

const APM_TRACE_EXPLORE_STYLE_ID = 'apm-trace-explore-runtime-style';
const APM_TRACE_EXPLORE_STYLE_TEXT = `
body .tippy-box[data-theme~='padding-0'] .tippy-content {
  padding: 0;
}

body .tippy-box[data-placement^='right'] .tippy-arrow {
  top: -8px !important;
}
`;

@Component
export default class ApmTraceHome extends tsc<any, any> {
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('timeRange') readonly timeRange: [string, string];
  @InjectReactive('timezone') readonly timezone: string;
  @InjectReactive('refreshInterval') readonly panelRefreshInterval: number;
  @InjectReactive('refreshImmediate') readonly panelRefreshImmediate: string;
  // 处理时间范围变化
  @Inject('handleTimeRangeChange') handleTimeRangeChange: (v: TimeRangeType) => void;
  @Inject({ from: 'handleCustomRouteQueryChange', default: () => {} }) handleCustomRouteQueryChange: (
    customRouteQuery: Record<string, number | string>
  ) => void;

  @Prop({ type: Object, default: null }) readonly slideDetail: null | {
    appName: string;
    bizId?: number;
    traceId: string;
  };

  runtimeStyleEl: HTMLStyleElement | null = null;

  get exploreQuery() {
    try {
      const query = this.$route.query || {};
      return {
        hasUrlWhere: 'traceWhere' in query,
        where: parseRouteJson(query.traceWhere, []),
        queryString: typeof query.traceQueryString === 'string' ? query.traceQueryString : '',
        filterMode: typeof query.traceFilterMode === 'string' ? query.traceFilterMode : 'ui',
        commonWhere: parseRouteJson(query.traceCommonWhere, []),
        selectedType: parseRouteJson(query.traceSelectedType, []),
      };
    } catch {
      return {
        hasUrlWhere: false,
        where: [],
        queryString: '',
        filterMode: 'ui',
        commonWhere: [],
        selectedType: [],
      };
    }
  }

  get v3Props() {
    return {
      viewOptions: this.viewOptions,
      timeRange: this.timeRange,
      timezone: this.timezone,
      refreshInterval: this.panelRefreshInterval,
      refreshImmediate: this.panelRefreshImmediate,
      slideDetail: this.slideDetail,
      exploreQuery: this.exploreQuery,
    };
  }

  syncExploreQueryToRoute(query: {
    commonWhere?: unknown[];
    filterMode?: string;
    queryString?: string;
    selectedType?: unknown[];
    where?: unknown[];
  }) {
    const nextQuery = {
      traceWhere: stringifyRouteJson(query.where || []),
      traceQueryString: query.queryString || '',
      traceFilterMode: query.filterMode || 'ui',
      traceCommonWhere: stringifyRouteJson(query.commonWhere || []),
      traceSelectedType: stringifyRouteJson(query.selectedType || []),
    };
    const currentQuery = this.$route.query || {};
    if (
      routeJsonUnchanged(currentQuery.traceWhere, query.where || []) &&
      String(currentQuery.traceQueryString || '') === nextQuery.traceQueryString &&
      String(currentQuery.traceFilterMode || 'ui') === nextQuery.traceFilterMode &&
      routeJsonUnchanged(currentQuery.traceCommonWhere, query.commonWhere || []) &&
      routeJsonUnchanged(currentQuery.traceSelectedType, query.selectedType || [])
    ) {
      return;
    }
    this.handleCustomRouteQueryChange(nextQuery);
  }

  handleV3EventChange(eventName: string, params: any) {
    if (eventName === 'exploreChartZoomChange') {
      this.handleTimeRangeChange(params as TimeRangeType);
      return;
    }

    if (eventName === 'exploreQueryChange') {
      this.syncExploreQueryToRoute(params || {});
      return;
    }

    if (eventName === 'sliderClose') {
      this.$emit('sliderClose');
    }
  }

  mounted() {
    this.injectRuntimeStyle();
  }

  beforeDestroy() {
    this.removeRuntimeStyle();
  }

  injectRuntimeStyle() {
    if (typeof document === 'undefined') return;
    const existedStyle = document.getElementById(APM_TRACE_EXPLORE_STYLE_ID) as HTMLStyleElement | null;
    if (existedStyle) {
      this.runtimeStyleEl = existedStyle;
      return;
    }
    const styleEl = document.createElement('style');
    styleEl.id = APM_TRACE_EXPLORE_STYLE_ID;
    styleEl.textContent = APM_TRACE_EXPLORE_STYLE_TEXT;
    document.head.appendChild(styleEl);
    this.runtimeStyleEl = styleEl;
  }

  removeRuntimeStyle() {
    if (!this.runtimeStyleEl) return;
    this.runtimeStyleEl.remove();
    this.runtimeStyleEl = null;
  }

  render() {
    return (
      <div
        id='apm-trace-home-main'
        class='apm-trace-home-page'
      >
        <TraceExplore
          v3Props={this.v3Props}
          onV3Event={this.handleV3EventChange}
        />
      </div>
    );
  }
}
