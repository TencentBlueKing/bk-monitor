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
import * as SceneViewApi from 'monitor-api/modules/scene_view';

interface ICustomTsGraphConfig {
  groups: {
    name: string;
    panels: {
      sub_title: string;
      targets: {
        alias: string;
        expression: string;
        function: Record<string, any>;
        metric: {
          alias: string;
          name: string;
        };
        query_configs: {
          data_label: string;
          data_source_label: string;
          data_type_label: string;
          filter_dict: {
            common_filter: Record<string, any>;
            group_filter: Record<string, any>;
          };
          functions: {
            id: string;
            params: {
              id: string;
              value: number;
            }[];
          }[];
          group_by: any[];
          interval: string;
          metrics: {
            alias: string;
            field: string;
            method: string;
          }[];
          table: string;
        }[];
        unit: string;
      }[];
      title: string;
    }[];
  }[];
}

interface ICustomTsMetricGroups {
  metric_groups: {
    common_dimensions: {
      alias: string;
      name: string;
    }[];
    metrics: {
      alias: string;
      dimensions: {
        alias: string;
        name: string;
      }[];
      field_id: number;
      metric_name: string;
    }[];
    name: string;
    scope_id: number;
  }[];
}

// 请求路径 'rest/v2/scene_view/get_custom_ts_metric_groups/'
export const getCustomTsMetricGroups = SceneViewApi.getCustomTsMetricGroups<
  {
    apm_app_name?: string;
    apm_service_name?: string;
    bk_biz_id?: number;
    time_series_group_id?: number;
  },
  ICustomTsMetricGroups
>;

// 请求路径 'rest/v2/scene_view/get_custom_ts_dimension_values/'
export const getCustomTsDimensionValues = SceneViewApi.getCustomTsDimensionValues<
  {
    apm_app_name?: string;
    apm_service_name?: string;
    bk_biz_id?: number;
    dimension: string;
    end_time: number;
    metrics: { name: string; scope_name: string }[];
    start_time: number;
    time_series_group_id?: number;
  },
  {
    alias: string;
    name: string;
  }[]
>;

// 请求路径 'rest/v2/scene_view/get_custom_ts_graph_config/'
export const getCustomTsGraphConfig = SceneViewApi.getCustomTsGraphConfig<
  {
    apm_app_name?: string;
    apm_service_name?: string;
    bk_biz_id?: number;
    end_time?: number;
    limit: {
      function: string;
      limit: number;
    };
    metrics: { name: string; scope_name: string }[];
    start_time?: number;
    time_series_group_id?: number;
    view_column?: number;
  },
  ICustomTsGraphConfig
>;

export const getSceneView = SceneViewApi.getSceneView<{
  common_conditions: {
    alias: string;
    key: string;
    method: 'eq' | 'exclude' | 'include' | 'neq' | 'nreg' | 'reg';
    value: string[];
  }[];
  compare: {
    offset: string[];
    type: '' | 'metric' | 'time';
  };
  group_by: {
    field: string;
    split: boolean;
  }[];
  interval: number | string;
  limit: {
    function: 'bottom' | 'top';
    limit: number;
  };
  metrics: string[];
  where: {
    condition: string;
    key: string;
    method: string;
    value: string[];
  }[];
}>;

export default {
  getCustomTsMetricGroups,
  getCustomTsDimensionValues,
  getCustomTsGraphConfig,
  getSceneView,
};
