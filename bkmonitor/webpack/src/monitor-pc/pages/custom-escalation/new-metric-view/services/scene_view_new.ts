/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import {
  getCustomTsMetricGroups as getCustomTsMetricGroupsApi,
  getCustomTsDimensionValues as getCustomTsDimensionValuesApi,
  getCustomTsGraphConfig as getCustomTsGraphConfigApi,
} from 'monitor-api/modules/scene_view';

/*
 * 查询指标分组信息
 */
export const getCustomTsMetricGroups: (params: { bk_biz_id?: number; time_series_group_id?: number }) => Promise<{
  common_dimensions: {
    alias: string;
    name: string;
  }[];
  metric_groups: {
    name: string;
    metrics: {
      alias: string;
      dimensions: {
        alias: string;
        name: string;
      }[];
      metric_name: string;
    }[];
  }[];
}> = getCustomTsMetricGroupsApi;

/*
 * 查询维度的候选值
 */
export const getCustomTsDimensionValues: (params: {
  bk_biz_id?: number;
  time_series_group_id: number;
  dimension: string;
  start_time: number;
  end_time: number;
  metrics: string[];
}) => Promise<{ name: string; alias: string }[]> = getCustomTsDimensionValuesApi;

/*
 * 获取图表配置
 */
export const getCustomTsGraphConfig: (params?: {
  bk_biz_id: number;
  time_series_group_id: number;
  metrics: string[];
  group_by: {
    field: string;
    split: boolean;
  }[];
  limit: {
    function: 'bottom' | 'top';
    limit: number;
  };
  conditions: {
    condition: 'and' | 'or';
    key: string;
    method: string;
    value: string[];
  }[];
  common_conditions?: {
    key: string;
    method: string;
    value: string[];
  }[];
  compare?: {
    /** ​ 对比类型：时间对比 | 指标对比 */
    type: 'metric' | 'time';
    /** ​ 时间偏移量 (如 1d=1天，2h=2小时) */
    offset: string[];
  };
  start_time: number;
  end_time: number;
}) => Promise<any> = getCustomTsGraphConfigApi;

export default {
  getCustomTsMetricGroups,
  getCustomTsDimensionValues,
  getCustomTsGraphConfig,
};
