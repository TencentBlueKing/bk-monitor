/* eslint-disable @typescript-eslint/naming-convention */
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

import { getMetricListV2 } from 'monitor-api/modules/strategies';

import { getMethodIdForLowerCase } from '../components/utils/utils';
import { MetricDetailV2, QueryConfig } from '../typings';
import { isVariableName } from '../variables/template/utils';

export const transformMetricId = (
  metricId: string,
  {
    data_source_label,
    data_type_label,
  }: {
    data_source_label?: string;
    data_type_label?: string;
  } = {}
) => {
  if (!metricId) return '';
  if (!(data_type_label === 'log' && data_source_label === 'bk_log_search')) return metricId;
  const sourceList = metricId.split('.');
  if (sourceList.length < 4) return metricId;
  return sourceList.slice(0, 3).join('.');
};

/**
 * 获取指标详情
 * @param queryConfigs 查询QueryConfig配置
 * @returns 指标详情 MetricDetailV2 实例列表
 */
export const fetchMetricDetailList = async (
  queryConfigs: Partial<Pick<QueryConfig, 'data_source_label' | 'data_type_label' | 'metric_id'>>[]
) => {
  const { metric_list } = await getMetricListV2<{
    metric_list: MetricDetailV2[];
  }>({
    conditions: [
      {
        key: 'metric_id',
        value: Array.from(
          new Set(
            queryConfigs.map(item =>
              transformMetricId(item.metric_id, {
                data_source_label: item.data_source_label,
                data_type_label: item.data_type_label,
              })
            )
          )
        ),
      },
    ],
  }).catch(() => ({ metric_list: [] as MetricDetailV2[] }));
  return metric_list.map(item => new MetricDetailV2(item));
};

const getMetricId = queryConfig => {
  return `${queryConfig?.data_source_label}.${queryConfig?.table}.${queryConfig.metrics?.[0]?.field}`;
};

export const createQueryTemplateQueryConfigsParams = (queryConfigs: QueryConfig[]) => {
  return queryConfigs
    .filter(item => !!item.metricDetail)
    .map(item => ({
      data_source_label: item.data_source_label,
      data_type_label: item.data_type_label,
      metric_id: item.metricDetail.metric_id,
      table: item.metricDetail.result_table_id,
      metrics: [
        {
          field: item.metricDetail.metric_field,
          method: item.agg_method,
          alias: item.alias || 'a',
        },
      ],
      group_by: item.agg_dimension,
      where:
        item.agg_condition?.map(w => {
          if (isVariableName(w.key)) {
            return w.key;
          }
          return w;
        }) || [],
      interval: item.agg_interval,
      functions:
        item.functions?.map(f => {
          if (isVariableName(f.id)) {
            return f.id;
          }
          return f;
        }) || [],
    }));
};

export const getRetrieveQueryTemplateQueryConfigs = async (query_configs: any[]): Promise<QueryConfig[]> => {
  const queryConfigs: QueryConfig[] = [];
  const metricList = await fetchMetricDetailList(
    query_configs.map(item => ({
      ...item,
      metric_id: item.metric_id || getMetricId(item),
    }))
  );
  for (const item of query_configs) {
    const metricId = item.metric_id || getMetricId(item);
    const metricDetail = metricList.find(metric => metric.metric_id === metricId);
    const queryConfig = new QueryConfig(
      metricDetail ||
        new MetricDetailV2({
          data_source_label: item.data_source_label,
          data_type_label: item.data_type_label,
          metric_field: item.metrics?.[0]?.field,
          metric_id: metricId,
          result_table_id: item.table,
          data_label: item.data_label,
          metric_field_name: item.metrics?.[0]?.field,
          dimensions: [],
        }),
      {
        agg_condition: item.where.map(w => {
          if (typeof w === 'string') {
            return {
              key: w,
              value: [],
              method: 'eq',
            };
          }
          return w;
        }),
        agg_dimension: item.group_by,
        functions: item.functions.map(f => {
          if (typeof f === 'string') {
            return {
              id: f,
              name: '',
              params: [],
            };
          }
          return f;
        }),
        metric_id: metricId,
        agg_interval: item.interval,
        alias: item.metrics?.[0]?.alias || 'a',
        agg_method: getMethodIdForLowerCase(item.metrics?.[0]?.method) || 'AVG',
      }
    );
    queryConfigs.push(queryConfig);
  }
  return queryConfigs;
};
