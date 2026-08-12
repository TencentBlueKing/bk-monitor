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
import { computed, reactive, shallowRef } from 'vue';

import { createGlobalState } from '@vueuse/core';

import {
  getIssueAiAnalysisOverview,
  getIssueSourceAnalysis,
  startIssueSourceAnalysis,
} from '../services/issues-ai-analysis';
import useRequestAbort from '@/hooks/useRequestAbort';

import type { AIAnalysisBaseParams, SourceAnalysisOverview, SourceAnalysisView } from '../typing';

export const useIssuesAiAnalysis = createGlobalState(() => {
  const sourceAnalysisData = shallowRef<SourceAnalysisOverview | SourceAnalysisView>(null);
  const loopStatus = ['pending', 'running'];
  const loading = reactive({
    sourceAnalysis: false,
    startAnalysis: false,
  });
  const sourceAnalysisScene = shallowRef<'overview' | 'view'>('overview');
  const sourceAnalysisIsPending = computed(() => loopStatus.includes(sourceAnalysisData.value?.latest?.status));
  let timer = null;

  const { run: overviewRun, signal: overviewSignal } = useRequestAbort(getIssueAiAnalysisOverview);
  const { run: sourceRun, signal: sourceSignal } = useRequestAbort(getIssueSourceAnalysis);

  const getSourceAnalysisData = async (params: AIAnalysisBaseParams) => {
    clearTimeout(timer);
    loading.sourceAnalysis = true;
    try {
      if (sourceAnalysisScene.value === 'overview') {
        const data = await overviewRun(params);
        if (overviewSignal?.aborted) return;
        sourceAnalysisData.value = data.source_analysis;
        console.log(3);
      } else {
        const data = await sourceRun(params);
        if (sourceSignal?.aborted) return;
        sourceAnalysisData.value = data;
      }
      console.log(2);
    } catch (err) {
      console.info('err', err);
    }
    if (sourceAnalysisIsPending.value) {
      timer = setTimeout(() => {
        getSourceAnalysisData(params);
      }, 3000);
    }
    console.log('1');
    loading.sourceAnalysis = false;
  };

  /**
   * 去配置
   */
  const handleToSetting = () => {};

  /**
   * 立即分析
   */
  const handleStartAnalysis = async (params: AIAnalysisBaseParams) => {
    loading.startAnalysis = true;
    sourceAnalysisData.value = await startIssueSourceAnalysis(params);
    loading.startAnalysis = false;
  };

  return {
    loading,
    sourceAnalysisScene,
    sourceAnalysisData,
    sourceAnalysisIsPending,
    getSourceAnalysisData,
    handleToSetting,
    handleStartAnalysis,
  };
});
