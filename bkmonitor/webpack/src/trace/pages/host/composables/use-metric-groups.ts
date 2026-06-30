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
import { ref as deepRef } from 'vue';

import { cloneDeep } from 'lodash';

import { MOCK_METRIC_GROUPS, MOCK_METRICS } from '../mock/metric-groups';

import type { MetricGroupModel, MetricItemModel } from '../types/metric-group';

export type MetricGroupsController = ReturnType<typeof useMetricGroups>;

/**
 * 指标分组与指标数据控制器。
 * 持有分组与指标的「已生效」数据，供「视图分组管理」编辑、图表后续消费。
 */
export function useMetricGroups() {
  const groups = deepRef<MetricGroupModel[]>(cloneDeep(MOCK_METRIC_GROUPS));
  const metrics = deepRef<MetricItemModel[]>(cloneDeep(MOCK_METRICS));

  /** 覆盖写入分组与指标（用于 Dialog 保存） */
  const setData = (nextGroups: MetricGroupModel[], nextMetrics: MetricItemModel[]) => {
    groups.value = nextGroups;
    metrics.value = nextMetrics;
  };

  /** 恢复默认（mock 初始数据） */
  const resetDefault = () => {
    groups.value = cloneDeep(MOCK_METRIC_GROUPS);
    metrics.value = cloneDeep(MOCK_METRICS);
  };

  return {
    groups,
    metrics,
    resetDefault,
    setData,
  };
}
