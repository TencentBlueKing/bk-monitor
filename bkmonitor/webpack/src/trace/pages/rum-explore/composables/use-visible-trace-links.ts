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
import { type MaybeRefOrGetter, onScopeDispose, shallowRef, toValue, watch } from 'vue';

import { searchTraceInfoMap, TRACE_SEARCH_BATCH_SIZE } from '../services/trace-link';

import type { IRumTraceInfo } from '../typings';

/** 每次重试递增的等待毫秒数。 */
const TRACE_RETRY_DELAY = 1000;
/** 单轮检索失败后的自动重试次数上限。 */
const TRACE_MAX_RETRIES = 2;

interface VisibleTraceLinkOptions {
  /** 表格或时间轴可交互时启用观察和新一批检索。 */
  active: MaybeRefOrGetter<boolean>;
  /** 发起全局检索的业务，省略时使用当前业务。 */
  bizId?: MaybeRefOrGetter<number | string | undefined>;
  /** 承载行元素的滚动容器，空值回落到浏览器视口。 */
  scrollRoot: MaybeRefOrGetter<Element | null>;
}

/**
 * @description 为 RUM 表格和时间轴批量检索可见行的关联 Trace，每收到一帧命中就更新入口。
 * @param {VisibleTraceLinkOptions} options 检索启用状态、业务和滚动容器
 * @returns 命中结果、行注册和结果集切换时的清理操作
 */
export function useVisibleTraceLinks({ active, bizId, scrollRoot }: VisibleTraceLinkOptions) {
  /** 按 Trace ID 保存已命中的详情定位信息，供入口逐帧更新。 */
  const traceInfoMap = shallowRef(new Map<string, IRumTraceInfo>());
  /** 等待发出请求或重试的 Trace ID。 */
  const traceQueue = new Set<string>();
  /** 已入队的 ID 含未命中的项，滚动和分页时无需重复检索。 */
  const queuedTraceIds = new Set<string>();
  /** 当前挂载的标记元素及对应 Trace ID，用于检测元素换绑。 */
  const observedRows = new Map<Element, string>();
  /** 当前滚动容器的行可见性观察器。 */
  let observer: IntersectionObserver | null = null;
  /** 当前检索轮次的中断控制器，同时防止队列被并发消费。 */
  let request: AbortController | null = null;
  /** 等待中的定时重试，清空后允许继续检索。 */
  let retryTimer: null | ReturnType<typeof setTimeout> = null;
  /** 当前队列已安排的自动重试次数，队列排空后归零。 */
  let retryCount = 0;

  /**
   * @description 为失败的请求安排有限重试，使持续可见的行也能恢复检索。
   * @returns {void}
   */
  function scheduleRetry() {
    if (retryCount >= TRACE_MAX_RETRIES) return;
    retryCount += 1;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      if (!toValue(active)) {
        retryCount -= 1;
        return;
      }
      void flushTraceQueue();
    }, TRACE_RETRY_DELAY * retryCount);
  }

  /**
   * @description 串行消费待检索的批次，同一轮请求共用中断信号。
   * @returns {Promise<void>} 当前轮次排空、中断或转入定时重试时完成
   */
  async function flushTraceQueue() {
    if (request || retryTimer !== null || !traceQueue.size || !toValue(active)) return;
    const controller = new AbortController();
    const { signal } = controller;
    request = controller;
    try {
      while (!signal.aborted && traceQueue.size && toValue(active)) {
        const batch = [...traceQueue].slice(0, TRACE_SEARCH_BATCH_SIZE);
        for (const traceId of batch) traceQueue.delete(traceId);
        try {
          await searchTraceInfoMap(
            batch,
            toValue(bizId) ?? window.cc_biz_id,
            infos => {
              if (signal.aborted) return;
              // 命中结果按帧替换 Map，触发 shallowRef 依赖的入口更新。
              const next = new Map(traceInfoMap.value);
              for (const info of infos) next.set(info.trace_id, info);
              traceInfoMap.value = next;
            },
            signal
          );
        } catch {
          if (signal.aborted) return;
          // 部分帧可能已经命中，只有剩余 ID 需要重试。
          for (const traceId of batch) {
            if (!traceInfoMap.value.has(traceId)) traceQueue.add(traceId);
          }
          if (traceQueue.size) {
            scheduleRetry();
            return;
          }
        }
      }
      if (!signal.aborted && !traceQueue.size) retryCount = 0;
    } finally {
      // 重置后可能已有新一轮检索，旧流只能释放自己的句柄。
      if (request === controller) request = null;
    }
  }

  /**
   * @description 将进入视口且尚未入队的 Trace ID 加入检索队列。
   * @param {IntersectionObserverEntry[]} entries 本次可见性变化的行
   * @param {IntersectionObserver} source 发出回调的观察器，用于识别重建前排队的回调
   * @returns {void}
   */
  function handleIntersect(entries: IntersectionObserverEntry[], source: IntersectionObserver) {
    // 观察器重建后，已排队的旧回调仍可能到达。
    if (source !== observer || !toValue(active)) return;
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const traceId = observedRows.get(entry.target);
      if (!traceId || queuedTraceIds.has(traceId)) continue;
      queuedTraceIds.add(traceId);
      traceQueue.add(traceId);
    }
    void flushTraceQueue();
  }

  /**
   * @description 断开当前观察器并释放实例，保留已注册的行供恢复观察。
   * @returns {void}
   */
  function disconnectObserver() {
    observer?.disconnect();
    observer = null;
  }

  /**
   * @description 根据启用状态和滚动容器调整观察器，容器变更后重新观察已注册的行。
   * @returns {void}
   */
  function updateObserver() {
    if (!toValue(active) || !observedRows.size) {
      disconnectObserver();
      return;
    }
    const root = toValue(scrollRoot) ?? null;
    if (observer?.root === root) return;
    disconnectObserver();
    observer = new IntersectionObserver(handleIntersect, { root });
    for (const row of observedRows.keys()) observer.observe(row);
  }

  /**
   * @description DOM 更新后同步整个列表的 Trace 标记，换绑 ID 的元素要重新观察。
   * @param {Element | null | undefined} container 含 data-trace-id 标记的列表容器，空值清理全部观察目标
   * @returns {void}
   */
  function observeRows(container: Element | null | undefined) {
    const nextRows = new Map<Element, string>();
    container?.querySelectorAll<HTMLElement>('[data-trace-id]').forEach(row => {
      if (row.dataset.traceId) nextRows.set(row, row.dataset.traceId);
    });
    for (const [row, traceId] of observedRows) {
      if (nextRows.get(row) === traceId) continue;
      observedRows.delete(row);
      observer?.unobserve(row);
    }
    for (const [row, traceId] of nextRows) {
      if (observedRows.has(row)) continue;
      observedRows.set(row, traceId);
      observer?.observe(row);
    }
    updateObserver();
  }

  watch([() => toValue(active), () => toValue(scrollRoot)], () => {
    updateObserver();
    void flushTraceQueue();
  });

  /**
   * @description 替换结果集或卸载时中断旧流，并清理重试、观察目标和检索缓存。
   * @returns {void}
   */
  function reset() {
    request?.abort();
    request = null;
    if (retryTimer !== null) clearTimeout(retryTimer);
    retryTimer = null;
    retryCount = 0;
    traceQueue.clear();
    queuedTraceIds.clear();
    traceInfoMap.value = new Map();
    observedRows.clear();
    disconnectObserver();
  }

  onScopeDispose(reset);
  return { observeRows, reset, traceInfoMap };
}
