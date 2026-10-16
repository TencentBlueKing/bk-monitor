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
import type { ProfileViewState } from '../types';

export function createViewState(): ProfileViewState {
  return {
    tab: 'application',
    graphMode: 'combined',
    traceMode: false,
    trendCollapsed: false,
    legend: {},
    keyword: '',
    highlight: '',
    direction: 'ltr',
    sort: { sortBy: 'total', descending: true },
    flameFocus: [],
    callGraph: { scale: 1, x: 0, y: 0 },
  };
}

export function restoreViewState(value: Partial<ProfileViewState> = {}): ProfileViewState {
  const defaults = createViewState();
  const input = value || {};
  const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
  return {
    tab: ['application', 'collection', 'file'].includes(input.tab) ? input.tab : defaults.tab,
    graphMode: ['table', 'combined', 'flame', 'callgraph'].includes(input.graphMode)
      ? input.graphMode
      : defaults.graphMode,
    traceMode: input.traceMode === true,
    trendCollapsed: input.trendCollapsed === true,
    legend:
      input.legend && typeof input.legend === 'object'
        ? Object.fromEntries(Object.entries(input.legend).filter(([, value]) => typeof value === 'boolean'))
        : {},
    keyword: typeof input.keyword === 'string' ? input.keyword : '',
    highlight: typeof input.highlight === 'string' ? input.highlight : '',
    direction: input.direction === 'rtl' ? 'rtl' : 'ltr',
    sort:
      input.sort && ['name', 'self', 'total', 'baseline', 'comparison', 'diff'].includes(input.sort.sortBy)
        ? { sortBy: input.sort.sortBy, descending: input.sort.descending === true }
        : defaults.sort,
    flameFocus:
      Array.isArray(input.flameFocus) && input.flameFocus.every(name => typeof name === 'string')
        ? input.flameFocus
        : [],
    callGraph: {
      scale: finite(input.callGraph?.scale) ? Math.min(8, Math.max(0.2, input.callGraph.scale)) : 1,
      x: finite(input.callGraph?.x) ? input.callGraph.x : 0,
      y: finite(input.callGraph?.y) ? input.callGraph.y : 0,
    },
  };
}
