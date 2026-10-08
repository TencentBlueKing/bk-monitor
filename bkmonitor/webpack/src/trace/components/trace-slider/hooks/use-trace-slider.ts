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
import { type MaybeRef, onScopeDispose, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';

import { DEFAULT_TRACE_DATA, QUERY_TRACE_RELATION_APP } from '@/store/constant';
import { useTraceStore } from '@/store/modules/trace';

import { fetchTraceSliderDetail } from '../services/trace-detail';

import type { TraceSliderDetailExpose } from '../typings';

export type UseTraceSliderReturn = ReturnType<typeof useTraceSlider>;

interface UseTraceSliderOptions {
  appName: MaybeRef<string | undefined>;
  bizId: MaybeRef<number | string | undefined>;
  isShow: MaybeRef<boolean>;
  traceId: MaybeRef<string | undefined>;
}

const resolveBizId = (bizId: number | string | undefined): number => {
  if (bizId != null && bizId !== '' && !Number.isNaN(+bizId)) {
    return +bizId;
  }
  return +(window.bk_biz_id || window.cc_biz_id);
};

/**
 * Trace 侧滑的取数与 store 写入。
 * TraceDetail 仍读全局 useTraceStore，这里只负责请求竞态、取消和关闭时复位，不改详情内部。
 */
export const useTraceSlider = (options: UseTraceSliderOptions) => {
  const store = useTraceStore();
  const fullscreen = shallowRef(false);
  const traceDetailRef = shallowRef<TraceSliderDetailExpose | null>(null);
  let searchCancelFn: (() => void) | null = null;

  const cancelPending = () => {
    searchCancelFn?.();
    searchCancelFn = null;
  };

  const resetTraceStore = () => {
    cancelPending();
    store.clearExternalLocateSpan();
    store.setTraceData(JSON.parse(JSON.stringify(DEFAULT_TRACE_DATA)));
  };

  const getTraceDetails = async () => {
    const appName = get(options.appName);
    const traceId = get(options.traceId);
    if (!appName || !traceId) return;

    cancelPending();
    store.setTraceDetail(true);
    store.setTraceLoaidng(true);

    const params: Parameters<typeof fetchTraceSliderDetail>[0] = {
      bk_biz_id: resolveBizId(get(options.bizId)),
      app_name: appName,
      trace_id: traceId,
    };

    const activePanel = traceDetailRef.value?.activePanel;
    if (
      activePanel !== 'statistics' &&
      (store.traceViewFilters.length > 1 ||
        (store.traceViewFilters.length === 1 && !store.traceViewFilters.includes('duration')))
    ) {
      const selects = store.traceViewFilters.filter(item => item !== 'duration' && item !== QUERY_TRACE_RELATION_APP);
      params.displays = ['source_category_opentelemetry'].concat(selects);
    }
    if (activePanel === 'timeline') {
      params.query_trace_relation_app = store.traceViewFilters.includes(QUERY_TRACE_RELATION_APP);
    }

    const { data, isAborted } = await fetchTraceSliderDetail(params, (cancel: () => void) => {
      searchCancelFn = cancel;
    });
    if (isAborted) return;
    if (data) {
      await store.setTraceData({ ...data, appName, trace_id: traceId });
    }
    store.setTraceLoaidng(false);
  };

  watch(
    () => [get(options.isShow), get(options.traceId), get(options.appName), get(options.bizId)] as const,
    ([isShow, traceId], previous) => {
      if (isShow && traceId) {
        getTraceDetails();
        return;
      }
      const wasShow = previous?.[0];
      // 仅从「打开」切到「关闭」时复位，避免组件以 isShow=false 挂载时冲掉宿主的 trace store
      if (!isShow && wasShow) {
        resetTraceStore();
      }
    },
    { immediate: true }
  );

  onScopeDispose(() => {
    cancelPending();
    if (get(options.isShow)) {
      resetTraceStore();
    }
    fullscreen.value = false;
  });

  const handleFullscreenChange = (flag: boolean) => {
    fullscreen.value = flag;
  };

  const handleSliderClose = () => {
    fullscreen.value = false;
    store.clearExternalLocateSpan();
  };

  return {
    fullscreen,
    handleFullscreenChange,
    handleSliderClose,
    traceDetailRef,
  };
};
