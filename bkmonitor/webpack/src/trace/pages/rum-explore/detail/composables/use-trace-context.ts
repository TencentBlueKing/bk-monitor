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
import { computed, onScopeDispose, shallowRef, unref, watch } from 'vue';
import type { InjectionKey, MaybeRef } from 'vue';

import { TIMELINE_REQUEST_RESOURCE_TYPES } from '../constants';
import { getViewTimeline, searchTraceInfoMap, TRACE_SEARCH_BATCH_SIZE } from '../services';
import { RumTimelineFilterCategoryEnum } from '../typings';
import { buildRecordMap, buildTimelineItems, buildViewVM, findSpanPath } from '../utils/timeline-transform';

import type { IRumTraceInfo } from '../services';
import type {
  IRumTimelineItemVM,
  IRumTimelineNode,
  IRumTimelineRecord,
  IRumTimelineResponse,
  IRumTimelineViewVM,
  RumTimelineFilterCategoryType,
} from '../typings';

/** 行可见性注册：上层按列表容器整批同步带 trace_id 的行，由抽屉 provide 给链路上下文面板 */
export type TraceContextRowsObserver = (root: Element) => void;

export const TRACE_CONTEXT_ROW_OBSERVER_KEY: InjectionKey<TraceContextRowsObserver> =
  Symbol('trace-context-rows-observer');

export type UseTraceContextReturn = ReturnType<typeof useTraceContext>;

interface IUseTraceContextOptions {
  /** 「链路上下文」tab 是否激活，未激活时不发请求 */
  active: MaybeRef<boolean>;
  appName: MaybeRef<string>;
  /** 业务 ID，用于检索关联 Trace 所属应用 */
  bizId: MaybeRef<number | string | undefined>;
  /** 当前详情的 span_id，决定高亮与折叠锚点 */
  currentSpanId: MaybeRef<string>;
  /** 抽屉里实际滚动的容器，作为行可见性观察的 root */
  scrollRoot: MaybeRef<Element | null>;
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
export function useTraceContext({
  active,
  appName,
  bizId,
  currentSpanId,
  formatField,
  scrollRoot,
  viewId,
}: IUseTraceContextOptions) {
  const timeline = shallowRef<IRumTimelineResponse | null>(null);
  const loading = shallowRef(false);
  /** 接口失败，与「无数据」区分展示 */
  const error = shallowRef(false);
  const expandedFolds = shallowRef(new Set<string>());
  const expandedNodes = shallowRef(new Set<string>());
  /** 关联 Trace 的检索结果：只有命中项才展示行内入口 */
  const traceInfoMap = shallowRef<Map<string, IRumTraceInfo>>(new Map());
  /** 请求序号，用于丢弃过期响应 */
  let requestId = 0;
  /** 已请求过的 `${appName}|${viewId}`，相同时不重复请求 */
  let fetchedKey = '';

  /** 待检索的 trace_id：行进入视口时入队，同一 View 内合并后按批发出 */
  let traceQueue = new Set<string>();
  /** 在途与已查完的 trace_id，避免重复检索（未命中的也记入） */
  let inflightTraceIds = new Set<string>();
  let resolvedTraceIds = new Set<string>();
  /** 队列代际：切换 View 或关闭抽屉后丢弃在途结果 */
  let traceQueueSeq = 0;
  let flushing = false;
  /** 当前这批检索的中断句柄 */
  let traceAbortController: AbortController | null = null;
  /** 检索失败的重试间隔与上限：整表都在视口内时不会再触发可见性回调，只能靠定时任务补齐 */
  const TRACE_RETRY_DELAY = 1000;
  const TRACE_RETRY_MAX_TIMES = 2;
  let traceRetryTimer: null | ReturnType<typeof setTimeout> = null;
  /** 本轮已重试的次数，队列排空后重置 */
  let traceRetryTimes = 0;

  /** 已注册观察的行元素与其 trace_id，root 变化时据此重新观察 */
  const observedRows = new Map<Element, string>();
  let rowObserver: IntersectionObserver | null = null;
  let observerRoot: Element | null = null;

  /** 增量合并一帧命中结果：shallowRef 的 Map 需要整体替换才会触发更新 */
  function mergeTraceInfos(infos: IRumTraceInfo[], seq: number) {
    if (seq !== traceQueueSeq || !infos.length) return;
    const next = new Map(traceInfoMap.value);
    for (const info of infos) next.set(info.trace_id, info);
    traceInfoMap.value = next;
  }

  function clearTraceRetry() {
    if (traceRetryTimer === null) return;
    clearTimeout(traceRetryTimer);
    traceRetryTimer = null;
  }

  /** 失败后按有限次数延迟重试：行一直留在视口内时不会有新的可见性回调来驱动队列 */
  function scheduleTraceRetry(seq: number) {
    if (seq !== traceQueueSeq || traceRetryTimer !== null || traceRetryTimes >= TRACE_RETRY_MAX_TIMES) return;
    traceRetryTimes += 1;
    traceRetryTimer = setTimeout(() => {
      traceRetryTimer = null;
      if (seq !== traceQueueSeq || !traceQueue.size) return;
      if (!unref(active)) {
        traceRetryTimes = Math.max(0, traceRetryTimes - 1);
        return;
      }
      void flushTraceQueue(seq);
    }, TRACE_RETRY_DELAY * traceRetryTimes);
  }

  /** 逐批检索入队的 trace_id，流里每收到一帧命中就立即合并，先有结果的行先展示入口 */
  async function flushTraceQueue(seq: number) {
    if (flushing) return;
    flushing = true;
    const controller = new AbortController();
    traceAbortController = controller;
    try {
      while (seq === traceQueueSeq && traceQueue.size) {
        const batch = [...traceQueue].slice(0, TRACE_SEARCH_BATCH_SIZE);
        for (const traceId of batch) {
          traceQueue.delete(traceId);
          inflightTraceIds.add(traceId);
        }
        try {
          await searchTraceInfoMap(
            batch,
            unref(bizId) ?? window.cc_biz_id,
            infos => mergeTraceInfos(infos, seq),
            controller.signal
          );
        } catch {
          /** 期间切换了 View 或关闭了抽屉，代际已变，本批交给新一轮，不能回写新队列 */
          if (seq !== traceQueueSeq) return;
          /** 检索失败：本批退回待检索并结束本轮，后续入队会把它一起带走；不同步重跑，避免连续打满失败接口 */
          for (const traceId of batch) {
            inflightTraceIds.delete(traceId);
            traceQueue.add(traceId);
          }
          scheduleTraceRetry(seq);
          break;
        }
        /** 期间切换了 View 或关闭了抽屉，剩余队列由新一轮接管 */
        if (seq !== traceQueueSeq) return;
        for (const traceId of batch) {
          inflightTraceIds.delete(traceId);
          resolvedTraceIds.add(traceId);
        }
      }
      /** 队列已排空，说明本轮没有遗留失败项，重置重试预算 */
      if (seq === traceQueueSeq && !traceQueue.size) {
        traceRetryTimes = 0;
        clearTraceRetry();
      }
    } finally {
      if (seq === traceQueueSeq) {
        flushing = false;
        traceAbortController = null;
      }
    }
  }

  /** 行进入视口时把关联 trace_id 入队，跳过在途与已查完的 ID */
  function enqueueTraceIds(traceIds: string[]) {
    for (const traceId of traceIds) {
      if (resolvedTraceIds.has(traceId) || inflightTraceIds.has(traceId) || traceQueue.has(traceId)) continue;
      traceQueue.add(traceId);
    }
    /** 队列里可能已有上一轮失败的遗留项，不只看本次是否新增 */
    if (!flushing && traceQueue.size) void flushTraceQueue(traceQueueSeq);
  }

  /** 清掉队列与在途检索：clearResult 为 true 时连已检索结果一起丢弃（切换 View） */
  function resetTraceQueue(clearResult: boolean) {
    traceQueueSeq++;
    traceQueue = new Set();
    inflightTraceIds = new Set();
    flushing = false;
    traceAbortController?.abort();
    traceAbortController = null;
    clearTraceRetry();
    traceRetryTimes = 0;
    if (clearResult) {
      resolvedTraceIds = new Set();
      traceInfoMap.value = new Map();
    }
    /** 旧 View 的行元素随之失效，新 View 的行挂载后重新注册 */
    observedRows.clear();
    rowObserver?.disconnect();
    rowObserver = null;
  }

  function handleRowIntersect(entries: IntersectionObserverEntry[]) {
    const entered: string[] = [];
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const traceId = observedRows.get(entry.target);
      if (traceId) entered.push(traceId);
    }
    if (entered.length) enqueueTraceIds(entered);
  }

  /** 按当前滚动容器创建观察器，root 变化时重建并重新观察已挂载的行 */
  function ensureRowObserver() {
    const root = unref(scrollRoot) ?? null;
    if (rowObserver && observerRoot === root) return rowObserver;
    rowObserver?.disconnect();
    observerRoot = root;
    rowObserver = new IntersectionObserver(handleRowIntersect, { root });
    for (const el of observedRows.keys()) rowObserver.observe(el);
    return rowObserver;
  }

  /**
   * 按列表容器整体同步行元素：新增的行开始观察，已移除的行注销。
   * 上层在列表渲染完成后调用一次，首屏、展开折叠行与滚动都命中同一观察器。
   */
  function observeTimelineRows(root: Element) {
    const rows = new Map<Element, string>();
    const elements = root.querySelectorAll<HTMLElement>('[data-trace-id]');
    for (let index = 0; index < elements.length; index += 1) {
      const el = elements[index];
      if (el.dataset.traceId) rows.set(el, el.dataset.traceId);
    }
    for (const el of observedRows.keys()) {
      if (rows.has(el)) continue;
      observedRows.delete(el);
      rowObserver?.unobserve(el);
    }
    for (const [el, traceId] of rows) {
      if (observedRows.get(el) === traceId) continue;
      observedRows.set(el, traceId);
      ensureRowObserver().observe(el);
    }
  }

  /** 滚动容器随抽屉重新渲染时（如切换 tab）重建观察器，行元素本身保持不变 */
  watch(
    () => unref(scrollRoot),
    () => {
      if (observedRows.size) ensureRowObserver();
    }
  );

  async function fetchTimeline(app: string, view: string) {
    const seq = ++requestId;
    loading.value = true;
    error.value = false;
    resetTraceQueue(true);
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
        resetTraceQueue(true);
        return;
      }
      fetchTimeline(app, view);
    },
    { immediate: true }
  );

  const recordMap = computed(() => buildRecordMap(timeline.value?.records));

  /** 快捷筛选：Span 名称关键字与类别，均为前端过滤 */
  const filterKeyword = shallowRef('');
  const filterCategory = shallowRef<RumTimelineFilterCategoryType>(RumTimelineFilterCategoryEnum.ALL);

  /** 慢节点阈值：耗时超过 500ms（elapsed_time 以微秒存储） */
  const SLOW_NODE_THRESHOLD_US = 500 * 1000;

  /** 类别筛选谓词，口径同 timeline 接口协议 2.12.3 */
  const CATEGORY_PREDICATES: Record<
    Exclude<RumTimelineFilterCategoryType, typeof RumTimelineFilterCategoryEnum.ALL>,
    (record: IRumTimelineRecord | undefined) => boolean
  > = {
    [RumTimelineFilterCategoryEnum.ACTION]: record =>
      String(record?.origin_data?.attributes?.span_type ?? '') === RumTimelineFilterCategoryEnum.ACTION,
    [RumTimelineFilterCategoryEnum.ERROR]: record => {
      const attributes: Record<string, unknown> = record?.origin_data?.attributes ?? {};
      return (
        String(attributes.span_type ?? '') === 'error' ||
        attributes.error === true ||
        attributes['outcome.type'] === 'error'
      );
    },
    [RumTimelineFilterCategoryEnum.SLOW_NODE]: record => {
      const elapsed = record?.origin_data?.elapsed_time;
      return elapsed !== null && elapsed !== undefined && Number(elapsed) > SLOW_NODE_THRESHOLD_US;
    },
    [RumTimelineFilterCategoryEnum.REQUEST]: record =>
      TIMELINE_REQUEST_RESOURCE_TYPES.has(record?.origin_data?.attributes?.['resource.type']),
    [RumTimelineFilterCategoryEnum.THIRD_PARTY]: record => {
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
    if (
      filterCategory.value !== RumTimelineFilterCategoryEnum.ALL &&
      !CATEGORY_PREDICATES[filterCategory.value](record)
    )
      return false;
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

  const hasFilter = computed(
    () => filterKeyword.value.trim() !== '' || filterCategory.value !== RumTimelineFilterCategoryEnum.ALL
  );

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
      traceInfoMap: traceInfoMap.value,
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

  /** 直接离开页面时组件卸载不会触发上面的 watch：补一次清理，中断在途检索并断开行观察器 */
  onScopeDispose(() => resetTraceQueue(false));

  return {
    loading,
    error,
    viewVM,
    items,
    handleExpandFold,
    handleToggleNode,
    observeTimelineRows,
    filterKeyword,
    filterCategory,
  };
}
