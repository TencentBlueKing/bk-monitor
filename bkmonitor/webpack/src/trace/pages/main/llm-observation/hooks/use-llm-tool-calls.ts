import { type ComputedRef, type InjectionKey, type Ref, computed, inject, shallowRef, watch } from 'vue';

import { listToolCalls } from 'monitor-api/modules/llm_web';

import { normalizeToolCall } from '../utils/match-tool-call';

import type { LlmToolCall } from '../utils/typings';

export const LLM_TOOL_CALL_MAP_KEY: InjectionKey<ComputedRef<Map<string, LlmToolCall>>> = Symbol('llm-tool-call-map');

/** 同一 app + Trace 只请求一次，失败不缓存以便重试 */
const toolCallCache = new Map<string, Promise<LlmToolCall[]>>();

function cacheKey(appName: string, traceId: string) {
  return `${appName}:${traceId}`;
}

function loadToolCalls(appName: string, traceId: string) {
  const key = cacheKey(appName, traceId);
  const cached = toolCallCache.get(key);
  if (cached) return cached;

  const pending = listToolCalls({ app_name: appName, trace_id: traceId }, { needMessage: false })
    .then((data: { tool_calls?: unknown } | undefined) => {
      if (!Array.isArray(data?.tool_calls)) return [];
      return data.tool_calls.map(normalizeToolCall).filter((item): item is LlmToolCall => Boolean(item));
    })
    .catch((error: unknown) => {
      toolCallCache.delete(key);
      throw error;
    });

  toolCallCache.set(key, pending);
  return pending;
}

/**
 * 按当前 Span 详情注入的 app / Trace 拉取工具调用，结果按 Trace 缓存。
 */
export function useLlmToolCalls() {
  const appName = inject<Ref<string>>('appName', shallowRef(''));
  const traceId = inject<Ref<string>>('traceId', shallowRef(''));
  const toolCalls = shallowRef<LlmToolCall[]>([]);
  let requestSeq = 0;

  watch(
    () => [appName.value, traceId.value],
    async ([nextAppName, nextTraceId]) => {
      const seq = ++requestSeq;
      if (!nextAppName || !nextTraceId) {
        toolCalls.value = [];
        return;
      }
      try {
        const list = await loadToolCalls(nextAppName, nextTraceId);
        if (seq !== requestSeq) return;
        toolCalls.value = list;
      } catch {
        if (seq !== requestSeq) return;
        toolCalls.value = [];
      }
    },
    { immediate: true }
  );

  return {
    toolCalls: computed(() => toolCalls.value),
  };
}
