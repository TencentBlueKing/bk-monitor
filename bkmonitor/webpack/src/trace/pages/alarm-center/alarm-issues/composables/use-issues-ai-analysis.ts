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
import { computed, reactive, shallowRef, watch } from 'vue';

import { createGlobalState } from '@vueuse/core';
import { bkUiMessage } from 'trace/common/message';
import { useI18n } from 'vue-i18n';

import {
  getIssueAiAnalysisOverview,
  getIssueSourceAnalysis,
  reanalyzeIssueSourceAnalysis,
  retryIssueSourceAnalysis,
  startIssueSourceAnalysis,
} from '../services/issues-ai-analysis';
import useRequestAbort from '@/hooks/useRequestAbort';

import type {
  AIAnalysisBaseParams,
  SourceAnalysisOverview,
  SourceAnalysisRetryParams,
  SourceAnalysisView,
} from '../typing';

export const useIssuesAiAnalysis = createGlobalState(() => {
  const { t } = useI18n();
  const sourceAnalysisData = shallowRef<SourceAnalysisOverview | SourceAnalysisView>(null);
  const loopStatus = ['pending', 'running'];
  const loading = reactive({
    /** 源码分析结果loading */
    sourceAnalysis: false,
    /** 重新分析loading */
    retryAnalysis: false,
  });
  const sourceAnalysisScene = shallowRef<'overview' | 'view'>('overview');
  const sourceAnalysisIsPending = computed(() => loopStatus.includes(sourceAnalysisData.value?.latest?.status));
  let timer = null;

  const overviewRequest = useRequestAbort(getIssueAiAnalysisOverview);
  const sourceRequest = useRequestAbort(getIssueSourceAnalysis);
  let requestSequence = 0;
  let activeContext: null | { params: AIAnalysisBaseParams } = null;

  const clearSetTimeout = () => {
    ++requestSequence;
    clearTimeout(timer);
    timer = null;
    activeContext = null;
    overviewRequest.abort();
    sourceRequest.abort();
    sourceAnalysisData.value = null;
    loading.sourceAnalysis = false;
    loading.retryAnalysis = false;
  };

  const getContext = ({ bk_biz_id, issue_id }: AIAnalysisBaseParams) => {
    if (activeContext && (activeContext.params.bk_biz_id !== bk_biz_id || activeContext.params.issue_id !== issue_id)) {
      clearSetTimeout();
    }
    activeContext ??= { params: { bk_biz_id, issue_id } };
    return activeContext;
  };

  const getSourceAnalysisData = async (params: AIAnalysisBaseParams) => {
    const context = getContext(params);
    const scene = sourceAnalysisScene.value;
    const sequence = ++requestSequence;
    const isCurrent = () =>
      activeContext === context && sequence === requestSequence && scene === sourceAnalysisScene.value;
    clearTimeout(timer);
    timer = null;
    overviewRequest.abort();
    sourceRequest.abort();
    if (!sourceAnalysisIsPending.value) {
      loading.sourceAnalysis = true;
    }
    try {
      if (scene === 'overview') {
        const data = await overviewRequest.run(context.params);
        if (!isCurrent()) return;
        sourceAnalysisData.value = data.source_analysis;
      } else {
        const data = await sourceRequest.run(context.params);
        if (!isCurrent()) return;
        sourceAnalysisData.value = data;
      }
    } catch (err) {
      if (!isCurrent()) return;
      console.info('err', err);
    } finally {
      if (isCurrent()) loading.sourceAnalysis = false;
    }
    if (isCurrent() && sourceAnalysisIsPending.value) {
      timer = setTimeout(() => {
        if (isCurrent()) getSourceAnalysisData(context.params);
      }, 3000);
    }
  };

  watch(
    sourceAnalysisScene,
    scene => {
      // 完整报告卸载后恢复概览轮询；侧滑已清理时不再发起请求。
      if (scene === 'overview' && activeContext) getSourceAnalysisData(activeContext.params);
    },
    { flush: 'sync' }
  );

  /**
   * 去配置
   */
  const handleToSetting = (bizId: number | string, blank = '') => {
    const { origin, pathname } = window.location;
    const url = `${origin}${pathname}?bizId=${bizId}#/ai-config?tab=source-code-analysis`;
    window.open(url, blank);
  };

  /**
   * 立即分析（第一次分析才调用这个接口）
   */
  const handleStartAnalysis = async (params: AIAnalysisBaseParams) => {
    const context = getContext(params);
    if (loading.retryAnalysis) return;
    loading.retryAnalysis = true;
    const data = await startIssueSourceAnalysis(params).finally(() => {
      if (activeContext === context) loading.retryAnalysis = false;
    });
    if (activeContext !== context) return;
    sourceAnalysisData.value = data;
    if (sourceAnalysisIsPending.value) {
      await getSourceAnalysisData(params);
    }
  };

  /**
   * 重新分析分为两种情况
   * 1. 失败重试（失败重试时，需要传递analysis_id）
   * 2. 重新分析（重新分析时，不需要传递analysis_id）
   */
  const handleReanalyzeSourceAnalysis = async (params: AIAnalysisBaseParams | SourceAnalysisRetryParams) => {
    const context = getContext(params);
    if (loading.retryAnalysis) return;
    loading.retryAnalysis = true;
    try {
      const options = { needMessage: false };
      const data =
        sourceAnalysisData.value.latest.status === 'failed'
          ? await retryIssueSourceAnalysis(params as SourceAnalysisRetryParams, options)
          : await reanalyzeIssueSourceAnalysis(params, options);
      if (activeContext !== context) return;
      sourceAnalysisData.value = data;
      bkUiMessage({ theme: 'success', message: t('分析任务已提交') });
      if (sourceAnalysisIsPending.value) {
        await getSourceAnalysisData({
          bk_biz_id: params.bk_biz_id,
          issue_id: params.issue_id,
        });
      }
    } catch (err) {
      if (activeContext !== context) return;
      const error = err?.data ?? err;
      const details = error?.error_details || (typeof error?.message === 'object' ? error.message : null);
      bkUiMessage({
        theme: 'error',
        message:
          (details?.popup_message && details) ||
          details?.overview ||
          (typeof error?.message === 'string' && error.message) ||
          (typeof error === 'string' && error) ||
          t('重新分析失败，请稍后重试'),
      });
    } finally {
      if (activeContext === context) loading.retryAnalysis = false;
    }
  };

  return {
    loading,
    sourceAnalysisScene,
    sourceAnalysisData,
    sourceAnalysisIsPending,
    getSourceAnalysisData,
    handleToSetting,
    handleStartAnalysis,
    handleReanalyzeSourceAnalysis,
    clearSetTimeout,
  };
});
