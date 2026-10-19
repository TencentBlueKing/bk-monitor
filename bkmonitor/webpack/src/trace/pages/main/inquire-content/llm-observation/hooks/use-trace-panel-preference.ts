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
    () =>
      [
        unref(context.hasLlmTraces),
        unref(context.llmLoading),
        unref(context.traceLoading),
        unref(context.traceId),
        storageKey.value,
      ] as const,
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
