/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type MaybeRef, computed, onScopeDispose, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { CancelToken } from 'monitor-api/cancel';
import { listFlows } from 'monitor-api/modules/llm_web';
import { useI18n } from 'vue-i18n';

import {
  buildStatCards,
  buildTraceView,
  collectSpanList,
  countSpanKinds,
  flattenVisibleSpanRows,
  pickConversationId,
} from '../utils/transform';

import type { LlmExecutionFilter, LlmFlowTrace, LlmOverviewStats, LlmSpanRowView, LlmTraceView } from '../utils/typings';

/** 供 TraceLlmObservation 解构的 hook 返回值类型 */
export type UseLlmObservationReturn = ReturnType<typeof useLlmObservation>;

/** 与 Trace 详情传入的 app / biz / trace 上下文绑定 */
type UseLlmObservationOptions = {
  appName: MaybeRef<string>;
  bizId: MaybeRef<number>;
  traceId: MaybeRef<string>;
};

/** 面板渲染用的 Trace 块：在 LlmTraceView 上附加懒加载状态与当前可见 Span 行 */
type TraceBlockView = LlmTraceView & {
  flowLoading: boolean;
  rows: LlmSpanRowView[];
};

/** 按会话维度聚合 Trace 列表（同 gen_ai.conversation.id） */
const LLM_CONVERSATION_GROUP_FIELD = 'attributes.gen_ai.conversation.id';
/** 按单条 Trace 拉取完整 Span 树 */
const LLM_TRACE_GROUP_FIELD = 'trace_id';
/** 会话概览 Trace 不超过该数量时，按文档异步预加载各条 flow */
const SESSION_FLOW_PRELOAD_LIMIT = 5;

/**
 * Trace 详情 LLM 观测的数据与交互状态。
 * - 默认按 trace_id 拉 overview + flow；开启「同会话」后按 conversation.id 拉多 Trace，flow 懒加载。
 * - Trace / Span 详情展开均为手风琴（同时仅一项展开）。
 */
export function useLlmObservation(options: UseLlmObservationOptions) {
  const { t } = useI18n();
  const loading = shallowRef(false);
  const traces = shallowRef<LlmFlowTrace[]>([]);
  const overviewStats = shallowRef<LlmOverviewStats | null>(null);
  const conversationId = shallowRef('');
  const showSession = shallowRef(false);
  const filter = shallowRef<LlmExecutionFilter>('all');
  const keyword = shallowRef('');
  const expandedTraceIds = shallowRef<Set<string>>(new Set());
  const expandedSpanIds = shallowRef<Set<string>>(new Set());
  const detailExpandedSpanIds = shallowRef<Set<string>>(new Set());
  const flowLoadedTraceIds = shallowRef<Set<string>>(new Set());
  const loadingTraceIds = shallowRef<Set<string>>(new Set());
  let cancelFetch = () => {};
  const cancelDetailFetches = new Map<string, () => void>();
  /** 递增以丢弃过期的 overview / 懒加载响应 */
  let overviewRequestId = 0;

  const stats = computed(() => buildStatCards(traces.value, t, overviewStats.value));
  const kindCounts = computed(() => countSpanKinds(traces.value));
  /** 仅对已展开的 Trace 计算 flatten 行；筛选/关键字变化时复算 rows，不重复请求接口 */
  const traceBlocks = computed<TraceBlockView[]>(() =>
    traces.value.map(item => {
      const view = buildTraceView(item, get(options.traceId), flowLoadedTraceIds.value.has(item.trace_id));
      const expanded = expandedTraceIds.value.has(item.trace_id);
      return {
        ...view,
        flowLoading: loadingTraceIds.value.has(item.trace_id),
        rows: expanded
          ? flattenVisibleSpanRows(item.flow, {
              expandedSpanIds: expandedSpanIds.value,
              filter: filter.value,
              keyword: keyword.value,
            })
          : [],
      };
    })
  );

  /** 会话时间线中当前 Trace 固定排在首位，便于与详情页上下文对齐 */
  const sortTraces = (nextTraces: LlmFlowTrace[], currentTraceId: string) =>
    [...nextTraces].sort((left, right) => {
      if (left.trace_id === currentTraceId) return -1;
      if (right.trace_id === currentTraceId) return 1;
      return 0;
    });

  const cancelAllDetailFetches = () => {
    for (const cancel of cancelDetailFetches.values()) cancel();
    cancelDetailFetches.clear();
    loadingTraceIds.value = new Set();
  };

  const markTraceLoading = (traceId: string, nextLoading: boolean) => {
    const next = new Set(loadingTraceIds.value);
    if (nextLoading) next.add(traceId);
    else next.delete(traceId);
    loadingTraceIds.value = next;
  };

  /** 会话模式刷新列表时保留已懒加载过的 flow，避免重复请求 */
  const mergeSessionTraces = (nextTraces: LlmFlowTrace[], prevTraces: LlmFlowTrace[], loadedIds: Set<string>) => {
    const prevMap = new Map(prevTraces.map(item => [item.trace_id, item]));
    return nextTraces.map(item => {
      if (item.flow?.length) return item;
      const prev = prevMap.get(item.trace_id);
      if (prev && loadedIds.has(item.trace_id)) {
        return { ...item, flow: prev.flow || [] };
      }
      return { ...item, flow: item.flow || [] };
    });
  };

  /** 会话模式下按 trace_id 二次请求，补齐该 Trace 的 Span 树 */
  const loadTraceFlow = async (traceId: string) => {
    const appName = get(options.appName);
    const bizId = get(options.bizId);
    if (!appName || !bizId || !traceId) return;
    if (flowLoadedTraceIds.value.has(traceId) || loadingTraceIds.value.has(traceId)) return;

    const requestId = overviewRequestId;
    markTraceLoading(traceId, true);
    try {
      const data = await listFlows(
        {
          bk_biz_id: bizId,
          app_name: appName,
          group_field: LLM_TRACE_GROUP_FIELD,
          group_id: traceId,
        },
        {
          cancelToken: new CancelToken((cancel: () => void) => {
            cancelDetailFetches.set(traceId, cancel);
          }),
        }
      );
      if (requestId !== overviewRequestId) return;
      if (!traces.value.some(item => item.trace_id === traceId)) return;

      const detail = data?.traces?.find(item => item.trace_id === traceId) || data?.traces?.[0];
      traces.value = traces.value.map(item =>
        item.trace_id === traceId ? { ...item, flow: detail?.flow || [] } : item
      );
      const nextLoaded = new Set(flowLoadedTraceIds.value);
      nextLoaded.add(traceId);
      flowLoadedTraceIds.value = nextLoaded;

      // flow 到达后默认展开全部 Span 子树，便于首屏看到完整执行线
      const nextSpanIds = new Set(expandedSpanIds.value);
      for (const span of collectSpanList(detail?.flow || [])) {
        nextSpanIds.add(span.span_id);
      }
      expandedSpanIds.value = nextSpanIds;
    } catch {
      /* 失败保持未加载，允许再次展开重试 */
    } finally {
      cancelDetailFetches.delete(traceId);
      markTraceLoading(traceId, false);
    }
  };

  /** 当前 Trace 必拉 flow；会话 Trace 数 ≤ 阈值时后台预拉其余条，减少展开等待 */
  const loadMissingSessionFlows = (nextTraces: LlmFlowTrace[], currentTraceId: string, loadedIds: Set<string>) => {
    const shouldPreload = nextTraces.length <= SESSION_FLOW_PRELOAD_LIMIT;
    for (const item of nextTraces) {
      if (loadedIds.has(item.trace_id)) continue;
      if (item.trace_id === currentTraceId || shouldPreload) {
        loadTraceFlow(item.trace_id);
      }
    }
  };

  /** 拉 overview：单 Trace 模式一次带回 flow；会话模式仅 Trace 列表，flow 另走 loadTraceFlow */
  const fetchFlows = async () => {
    const appName = get(options.appName);
    const traceId = get(options.traceId);
    const bizId = get(options.bizId);
    if (!appName || !traceId || !bizId) {
      traces.value = [];
      overviewStats.value = null;
      flowLoadedTraceIds.value = new Set();
      return;
    }

    cancelFetch();
    cancelAllDetailFetches();
    const requestId = ++overviewRequestId;
    loading.value = true;
    try {
      const useSession = showSession.value && Boolean(conversationId.value);
      const data = await listFlows(
        {
          bk_biz_id: bizId,
          app_name: appName,
          group_field: useSession ? LLM_CONVERSATION_GROUP_FIELD : LLM_TRACE_GROUP_FIELD,
          group_id: useSession ? conversationId.value : traceId,
        },
        {
          cancelToken: new CancelToken((cancel: () => void) => {
            cancelFetch = cancel;
          }),
        }
      );
      if (requestId !== overviewRequestId) return;

      const nextTraces = sortTraces(data?.traces || [], traceId);
      const merged = useSession
        ? mergeSessionTraces(nextTraces, traces.value, flowLoadedTraceIds.value)
        : nextTraces.map(item => ({ ...item, flow: item.flow || [] }));
      traces.value = merged;
      overviewStats.value = data || null;
      if (!conversationId.value) {
        conversationId.value = pickConversationId(merged);
      }

      const loaded = new Set<string>();
      if (useSession) {
        for (const item of merged) {
          if (item.flow?.length || flowLoadedTraceIds.value.has(item.trace_id)) {
            loaded.add(item.trace_id);
          }
        }
      } else {
        for (const item of merged) loaded.add(item.trace_id);
      }
      flowLoadedTraceIds.value = loaded;
      syncExpandedState(merged, traceId);

      if (useSession) {
        loadMissingSessionFlows(merged, traceId, loaded);
      }
    } catch {
      if (requestId !== overviewRequestId) return;
      traces.value = [];
      overviewStats.value = null;
      flowLoadedTraceIds.value = new Set();
    } finally {
      if (requestId === overviewRequestId) {
        loading.value = false;
      }
    }
  };

  /** 概览刷新后：仅展开当前 Trace，并展开其下全部 Span */
  const syncExpandedState = (nextTraces: LlmFlowTrace[], currentTraceId: string) => {
    const nextTraceIds = new Set<string>([currentTraceId]);
    const nextSpanIds = new Set<string>();
    for (const item of nextTraces) {
      if (item.trace_id === currentTraceId) {
        for (const span of collectSpanList(item.flow)) {
          nextSpanIds.add(span.span_id);
        }
      }
    }
    expandedTraceIds.value = nextTraceIds;
    expandedSpanIds.value = nextSpanIds;
    detailExpandedSpanIds.value = new Set();
  };

  const handleSessionChange = (checked: boolean) => {
    showSession.value = checked;
  };

  const handleFilterChange = (next: LlmExecutionFilter) => {
    filter.value = next;
  };

  const handleKeywordChange = (value: string) => {
    keyword.value = value;
  };

  /** Trace 块手风琴：再次点击已展开项则全部收起 */
  const toggleTrace = (traceId: string) => {
    if (expandedTraceIds.value.has(traceId)) {
      expandedTraceIds.value = new Set();
      return;
    }
    expandedTraceIds.value = new Set([traceId]);
    if (!flowLoadedTraceIds.value.has(traceId)) {
      loadTraceFlow(traceId);
    }
  };

  /** Span 子树可多选展开；与 Trace 块、行内详情的手风琴互不影响 */
  const toggleSpan = (spanId: string) => {
    const next = new Set(expandedSpanIds.value);
    if (next.has(spanId)) next.delete(spanId);
    else next.add(spanId);
    expandedSpanIds.value = next;
  };

  /** Span 行内详情面板手风琴 */
  const toggleDetail = (spanId: string) => {
    if (detailExpandedSpanIds.value.has(spanId)) {
      detailExpandedSpanIds.value = new Set();
      return;
    }
    detailExpandedSpanIds.value = new Set([spanId]);
  };

  /** 切换 Trace / 应用 / 空间时清空会话模式与筛选，避免沿用上一 Trace 的 UI 状态 */
  watch(
    () => [get(options.appName), get(options.traceId), get(options.bizId)] as const,
    () => {
      conversationId.value = '';
      showSession.value = false;
      filter.value = 'all';
      keyword.value = '';
      overviewStats.value = null;
      flowLoadedTraceIds.value = new Set();
      loadingTraceIds.value = new Set();
    }
  );

  /** showSession 切换会改 group_field，需重新拉 overview；immediate 覆盖首屏进入 */
  watch(
    () => [get(options.appName), get(options.traceId), get(options.bizId), showSession.value] as const,
    ([, traceId]) => {
      if (!traceId) {
        traces.value = [];
        overviewStats.value = null;
        flowLoadedTraceIds.value = new Set();
        return;
      }
      fetchFlows();
    },
    { immediate: true }
  );

  onScopeDispose(() => {
    cancelFetch();
    cancelAllDetailFetches();
  });

  return {
    conversationId,
    detailExpandedSpanIds,
    expandedSpanIds,
    expandedTraceIds,
    filter,
    handleFilterChange,
    handleKeywordChange,
    handleSessionChange,
    keyword,
    kindCounts,
    loading,
    showSession,
    stats,
    toggleDetail,
    toggleSpan,
    toggleTrace,
    traceBlocks,
  };
}
