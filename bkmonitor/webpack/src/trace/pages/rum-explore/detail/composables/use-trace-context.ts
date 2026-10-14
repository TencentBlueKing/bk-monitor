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
import { computed, shallowRef, unref, watch } from 'vue';
import type { MaybeRef } from 'vue';

import { getViewTimeline } from '../services';
import { buildRecordMap, buildTimelineItems, buildViewVM, findSpanPath } from '../utils/timeline-transform';

import type { IRumTimelineItemVM, IRumTimelineResponse, IRumTimelineViewVM } from '../typings';

export type UseTraceContextReturn = ReturnType<typeof useTraceContext>;

interface IUseTraceContextOptions {
  /** 「链路上下文」tab 是否激活，未激活时不发请求 */
  active: MaybeRef<boolean>;
  appName: MaybeRef<string>;
  /** 当前详情的 span_id，决定高亮与折叠锚点 */
  currentSpanId: MaybeRef<string>;
  /** 当前 Span 所属的 View ID，为空时不请求 */
  viewId: MaybeRef<string>;
  /** 字段格式化函数，来自 useDetailFormatter */
  formatField: (fieldName: string, value: unknown) => string;
}

/**
 * @description 链路上下文：按 View 拉取时间线，维护折叠段与子节点的展开状态，产出可直接渲染的视图模型
 *
 * 同一 View 下切换 Span（上一个 / 下一个）不重复请求，只重新定位高亮与折叠锚点。
 */
export function useTraceContext({ active, appName, currentSpanId, formatField, viewId }: IUseTraceContextOptions) {
  const timeline = shallowRef<IRumTimelineResponse | null>(null);
  const loading = shallowRef(false);
  /** 接口失败，与「无数据」区分展示 */
  const error = shallowRef(false);
  const expandedFolds = shallowRef(new Set<string>());
  const expandedNodes = shallowRef(new Set<string>());
  /** 请求序号，用于丢弃过期响应 */
  let requestId = 0;
  /** 已请求过的 `${appName}|${viewId}`，相同时不重复请求 */
  let fetchedKey = '';

  async function fetchTimeline(app: string, view: string) {
    const seq = ++requestId;
    loading.value = true;
    error.value = false;
    const res = await getViewTimeline({ app_name: app, view_id: view });
    if (seq !== requestId) return;
    timeline.value = res;
    error.value = !res;
    loading.value = false;
  }

  watch(
    () => [unref(active), unref(appName), unref(viewId)] as const,
    ([isActive, app, view]) => {
      if (!isActive) return;
      const key = `${app}|${view}`;
      if (key === fetchedKey) return;
      fetchedKey = key;
      if (!view) {
        requestId++;
        timeline.value = null;
        error.value = false;
        loading.value = false;
        return;
      }
      fetchTimeline(app, view);
    },
    { immediate: true }
  );

  const recordMap = computed(() => buildRecordMap(timeline.value?.records));
  /** 按 view_id 查询时只有一个顶层 View 节点 */
  const viewNode = computed(() => timeline.value?.tree?.[0] ?? null);
  const currentPath = computed(() => findSpanPath(timeline.value?.tree, unref(currentSpanId)));

  /** 数据或当前 Span 变化时重置展开状态：折叠段全部收起，只展开当前 Span 的祖先节点 */
  watch(
    currentPath,
    path => {
      expandedFolds.value = new Set();
      expandedNodes.value = new Set(path.slice(0, -1));
    },
    { immediate: true }
  );

  const viewVM = computed<IRumTimelineViewVM | null>(() =>
    viewNode.value ? buildViewVM(viewNode.value, recordMap.value, unref(currentSpanId), formatField) : null
  );

  const items = computed<IRumTimelineItemVM[]>(() =>
    buildTimelineItems(viewNode.value?.children, {
      recordMap: recordMap.value,
      currentSpanId: unref(currentSpanId),
      currentPath: new Set(currentPath.value),
      expandedFolds: expandedFolds.value,
      expandedNodes: expandedNodes.value,
    })
  );

  /** 展开一段折叠的 Span */
  const handleExpandFold = (key: string) => {
    expandedFolds.value = new Set(expandedFolds.value).add(key);
  };

  /** 切换节点子级的展开 / 收起 */
  const handleToggleNode = (spanId: string) => {
    const next = new Set(expandedNodes.value);
    if (next.has(spanId)) {
      next.delete(spanId);
    } else {
      next.add(spanId);
    }
    expandedNodes.value = next;
  };

  return { loading, error, viewVM, items, handleExpandFold, handleToggleNode };
}
