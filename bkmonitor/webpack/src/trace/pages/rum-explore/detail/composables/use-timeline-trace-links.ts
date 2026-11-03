import { onBeforeUnmount, shallowRef, unref, watch } from 'vue';
import type { MaybeRef } from 'vue';

import { streamTraceInfos } from '../services/trace-link';

import type { IRumTraceInfo } from '../services/trace-link';

const TRACE_BATCH_SIZE = 20;

/** 可见 Resource 的 TraceID 去重排队，同一时间只保留一批流式检索。 */
export function useTimelineTraceLinks(scopeKey: MaybeRef<string>, bizId: MaybeRef<number | string>) {
  const traceLinks = shallowRef(new Map<string, IRumTraceInfo[]>());
  const queued = new Set<string>();
  const requested = new Set<string>();
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function schedule() {
    if (!queued.size || controller || timer !== undefined) return;
    timer = setTimeout(fetchBatch, 0);
  }

  async function fetchBatch() {
    timer = undefined;
    const traceIds = [...queued].slice(0, TRACE_BATCH_SIZE);
    for (const traceId of traceIds) queued.delete(traceId);
    const batchController = new AbortController();
    controller = batchController;
    try {
      await streamTraceInfos(
        traceIds,
        unref(bizId),
        items => {
          if (batchController.signal.aborted) return;
          const grouped = new Map<string, IRumTraceInfo[]>();
          for (const item of items) {
            const links = grouped.get(item.trace_id) ?? [];
            links.push(item);
            grouped.set(item.trace_id, links);
          }
          traceLinks.value = new Map([...traceLinks.value, ...grouped]);
        },
        batchController.signal
      );
    } finally {
      if (controller === batchController) {
        controller = null;
        schedule();
      }
    }
  }

  function enqueueTraceIds(traceIds: string[]) {
    for (const traceId of traceIds) {
      if (requested.has(traceId) || !/^[0-9a-z]{32}$/.test(traceId)) continue;
      requested.add(traceId);
      queued.add(traceId);
    }
    schedule();
  }

  function reset() {
    controller?.abort();
    controller = null;
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
    queued.clear();
    requested.clear();
    traceLinks.value = new Map();
  }

  watch(() => [unref(scopeKey), unref(bizId)], reset, { flush: 'sync' });
  onBeforeUnmount(reset);

  return { traceLinks, enqueueTraceIds };
}
