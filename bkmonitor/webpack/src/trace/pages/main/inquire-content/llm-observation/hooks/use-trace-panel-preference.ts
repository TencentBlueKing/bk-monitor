import { type MaybeRef, computed, onScopeDispose, shallowRef, unref, watch } from 'vue';

type PanelContext = {
  appName: MaybeRef<string>;
  bizId: MaybeRef<number>;
  hasLlmTraces: MaybeRef<boolean>;
  llmLoading: MaybeRef<boolean>;
  traceId: MaybeRef<string>;
  traceLoading?: MaybeRef<boolean>;
};

/** 每个业务、应用记住 LLM/瀑布偏好，异步结果不覆盖用户本次手动选择。 */
export function useTracePanelPreference(context: PanelContext) {
  const panel = shallowRef('timeline');
  const storageKey = computed(() => `trace_detail_panel:${unref(context.bizId)}:${unref(context.appName)}`);
  let preferredPanel = 'llm';
  let hasSelected = false;
  let usedFallback = false;
  let fallbackTimer: ReturnType<typeof setTimeout> | undefined;
  const clearFallbackTimer = () => {
    clearTimeout(fallbackTimer);
    fallbackTimer = undefined;
  };
  onScopeDispose(clearFallbackTimer);

  watch(
    () => [unref(context.appName), unref(context.traceId), unref(context.bizId)],
    () => {
      clearFallbackTimer();
      hasSelected = false;
      usedFallback = false;
      panel.value = 'timeline';
      try {
        preferredPanel = localStorage.getItem(storageKey.value) === 'timeline' ? 'timeline' : 'llm';
      } catch {
        preferredPanel = 'llm';
      }
    },
    { immediate: true }
  );

  watch(
    () => [unref(context.hasLlmTraces), unref(context.llmLoading), unref(context.traceLoading),
      unref(context.traceId), storageKey.value] as const,
    ([hasTraces, loading, traceLoading]) => {
      if (hasSelected) return;
      if (!hasTraces) {
        clearFallbackTimer();
        if (!loading) panel.value = 'timeline';
        return;
      }
      if (preferredPanel === 'llm' || usedFallback) {
        clearFallbackTimer();
        panel.value = 'llm';
      } else if (!traceLoading) {
        clearFallbackTimer();
        panel.value = 'timeline';
      } else if (fallbackTimer === undefined) {
        fallbackTimer = setTimeout(() => {
          fallbackTimer = undefined;
          if (!hasSelected && unref(context.hasLlmTraces) && unref(context.traceLoading)) {
            usedFallback = true;
            panel.value = 'llm';
          }
        }, 500);
      }
    },
    { immediate: true }
  );

  const selectPanel = (value: string) => {
    clearFallbackTimer();
    hasSelected = true;
    panel.value = value;
    if (value === 'llm' || value === 'timeline') {
      preferredPanel = value;
      try {
        localStorage.setItem(storageKey.value, value);
      } catch {
        // 浏览器禁用存储时仍允许切换视图。
      }
    }
  };

  return { panel, selectPanel };
}
