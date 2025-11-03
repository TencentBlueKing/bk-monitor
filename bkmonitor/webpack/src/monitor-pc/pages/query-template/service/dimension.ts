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

import { getVariableValue } from 'monitor-api/modules/grafana';

import type { DimensionValue, MetricDetailV2 } from '../typings';

/**
 * 获取指标维度值列表
 * @param dimension 维度
 * @param data 关联指标数据
 * @returns 维度值列表
 */
export const fetchMetricDimensionValueList = async (
  dimension: string,
  data: Pick<MetricDetailV2, 'data_source_label' | 'data_type_label' | 'metric_field' | 'result_table_id'>
) => {
  const valueList = await getVariableValue<DimensionValue[]>({
    params: {
      data_source_label: data.data_source_label,
      data_type_label: data.data_type_label,
      field: dimension,
      metric_field: data.metric_field,
      result_table_id: data.result_table_id,
      where: [],
    },
    type: 'dimension',
  }).catch(() => [] as DimensionValue[]);
  return valueList;
};
