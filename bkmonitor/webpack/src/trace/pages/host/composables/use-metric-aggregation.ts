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
import { computed, reactive } from 'vue';

import { DEFAULT_AGGREGATION_STATE } from '../constants/aggregation';

import type { MetricAggregationState } from '../types/aggregation';
import type { ChartViewOptions } from '@/pages/trace-explore/components/explore-chart/use-chart-view-option';

export type MetricAggregationController = ReturnType<typeof useMetricAggregation>;

/**
 * 指标汇聚 Toolbar 状态控制器。
 * 由「指标汇聚」Tab 容器持有，向 Toolbar（受控）与后续图表（props）统一分发。
 */
export function useMetricAggregation() {
  const state = reactive<MetricAggregationState>({ ...DEFAULT_AGGREGATION_STATE });

  /** 局部更新状态 */
  const updateState = (patch: Partial<MetricAggregationState>) => {
    Object.assign(state, patch);
  };

  /**
   * 查询参数：变更需要重新拉取图表数据的字段集合。
   * 下游图表只需 watch 此对象（deep），即可避免纯视图变更（如搜索/列数）触发无谓请求。
   */
  const queryParams = computed(() => ({
    interval: state.interval,
    method: state.method,
    compareType: state.compareType,
    compareTargets: state.compareTargets,
    timeShift: state.timeShift,
  }));

  /**
   * 纯视图选项：仅影响前端展示、不触发请求的字段集合。
   * 下游直接消费即可，无需 watch 后重新请求。
   */
  const viewOptions = computed<ChartViewOptions>(() => ({
    keyword: state.keyword,
    showStatistics: state.showStatistics,
    highlightPeak: state.highlightPeak,
    columns: state.columns,
  }));

  return {
    state,
    updateState,
    queryParams,
    viewOptions,
  };
}
