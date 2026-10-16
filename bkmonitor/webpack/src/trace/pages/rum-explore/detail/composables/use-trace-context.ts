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

import { TIMELINE_REQUEST_RESOURCE_TYPES } from '../constants';
import { getViewTimeline } from '../services';
import { buildRecordMap, buildTimelineItems, buildViewVM, findSpanPath } from '../utils/timeline-transform';

import type {
  IRumTimelineItemVM,
  IRumTimelineNode,
  IRumTimelineRecord,
  IRumTimelineResponse,
  IRumTimelineViewVM,
  RumTimelineFilterCategoryType,
} from '../typings';

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

  /** 快捷筛选：Span 名称关键字与类别，均为前端过滤 */
  const filterKeyword = shallowRef('');
  const filterCategory = shallowRef<RumTimelineFilterCategoryType>('all');

  /** 慢节点阈值：耗时超过 500ms（elapsed_time 以微秒存储） */
  const SLOW_NODE_THRESHOLD_US = 500 * 1000;

  /** 类别筛选谓词，口径同 timeline 接口协议 2.12.3 */
  const CATEGORY_PREDICATES: Record<
    Exclude<RumTimelineFilterCategoryType, 'all'>,
    (record: IRumTimelineRecord | undefined) => boolean
  > = {
    action: record => String(record?.origin_data?.attributes?.span_type ?? '') === 'action',
    error: record => {
      const attributes: Record<string, unknown> = record?.origin_data?.attributes ?? {};
      return (
        String(attributes.span_type ?? '') === 'error' ||
        attributes.error === true ||
        attributes['outcome.type'] === 'error'
      );
    },
    slow_node: record => {
      const elapsed = record?.origin_data?.elapsed_time;
      return elapsed !== null && elapsed !== undefined && Number(elapsed) > SLOW_NODE_THRESHOLD_US;
    },
    request: record => TIMELINE_REQUEST_RESOURCE_TYPES.has(record?.origin_data?.attributes?.['resource.type']),
    third_party: record => {
      const attributes: Record<string, unknown> = record?.origin_data?.attributes ?? {};
      return (
        String(attributes.span_type ?? '') === 'resource' &&
        !TIMELINE_REQUEST_RESOURCE_TYPES.has(String(attributes['resource.type'] ?? ''))
      );
    },
  };

  /** 节点是否命中当前筛选条件 */
  function matchRecord(record: IRumTimelineRecord | undefined) {
    const keyword = filterKeyword.value.trim().toLowerCase();
    if (
      keyword &&
      !String(record?.origin_data?.span_name ?? '')
        .toLowerCase()
        .includes(keyword)
    )
      return false;
    if (filterCategory.value !== 'all' && !CATEGORY_PREDICATES[filterCategory.value](record)) return false;
    return true;
  }

  /** 保留命中的节点与其祖先链，未命中子树整枝裁掉 */
  function filterNodes(nodes: IRumTimelineNode[] = []): IRumTimelineNode[] {
    const result: IRumTimelineNode[] = [];
    for (const node of nodes) {
      const children = filterNodes(node.children);
      if (matchRecord(recordMap.value.get(node.span_id)) || children.length) {
        result.push({ ...node, children });
      }
    }
    return result;
  }

  const hasFilter = computed(() => filterKeyword.value.trim() !== '' || filterCategory.value !== 'all');

  /** 筛选生效时只渲染过滤后的子树，不再出现折叠段，子级展开仍由 expandedNodes 控制 */
  const filteredChildren = computed(() =>
    hasFilter.value ? filterNodes(viewNode.value?.children) : viewNode.value?.children
  );

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

  /** 筛选生效时默认展开过滤结果的全部祖先，保证命中可见，之后仍可手动收起；筛选取消时恢复默认展开状态 */
  watch([hasFilter, filteredChildren], ([filterActive, nodes]) => {
    if (!filterActive) {
      expandedFolds.value = new Set();
      expandedNodes.value = new Set(currentPath.value.slice(0, -1));
      return;
    }
    const next = new Set<string>();
    const collectExpandable = (list?: IRumTimelineNode[]) => {
      for (const node of list ?? []) {
        if (node.children?.length) {
          next.add(node.span_id);
          collectExpandable(node.children);
        }
      }
    };
    collectExpandable(nodes);
    expandedNodes.value = next;
  });

  const viewVM = computed<IRumTimelineViewVM | null>(() =>
    viewNode.value ? buildViewVM(viewNode.value, recordMap.value, unref(currentSpanId), formatField) : null
  );

  const items = computed<IRumTimelineItemVM[]>(() =>
    buildTimelineItems(filteredChildren.value, {
      recordMap: recordMap.value,
      currentSpanId: unref(currentSpanId),
      currentPath: new Set(currentPath.value),
      expandedFolds: expandedFolds.value,
      expandedNodes: expandedNodes.value,
      showAll: hasFilter.value,
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

  return {
    loading,
    error,
    viewVM,
    items,
    handleExpandFold,
    handleToggleNode,
    filterKeyword,
    filterCategory,
  };
}
