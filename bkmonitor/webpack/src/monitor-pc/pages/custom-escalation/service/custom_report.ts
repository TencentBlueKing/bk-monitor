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
import * as CustomReportApi from 'monitor-api/modules/custom_report';

export interface ICustomTimeSeriesDetail {
  access_token: string;
  auto_discover: boolean;
  bk_biz_id: number;
  bk_data_id: number;
  bk_tenant_id: string;
  create_time: string;
  create_user: string;
  data_label: string;
  desc: string;
  is_deleted: boolean;
  is_platform: boolean;
  is_readonly: boolean;
  name: string;
  protocol: string;
  scenario: string;
  scenario_display: string[];
  table_id: string;
  target: any[];
  time_series_group_id: number;
  update_time: string;
  update_user: string;
  last_time?: string;
  metric_json: {
    fields: {
      aggregate_method: string;
      description: string;
      dimension_list: {
        id: string;
        name: string;
      }[];
      label: string[];
      monitor_type: string;
      name: string;
      type: string;
      unit: string;
    }[];
  }[];
}

export interface ICustomTimeSeriesList {
  list: {
    auto_discover: boolean;
    bk_biz_id: number;
    bk_data_id: number;
    bk_tenant_id: string;
    create_time: string;
    create_user: string;
    data_label: string;
    desc: string;
    is_deleted: boolean;
    is_platform: boolean;
    is_readonly: boolean;
    name: string;
    protocol: string;
    related_strategy_count: number;
    scenario: string;
    scenario_display: string[];
    table_id: string;
    time_series_group_id: number;
    update_time: string;
    update_user: string;
  }[];
}

export interface ICustomTsFields {
  dimensions: {
    config: {
      alias: string;
      common: boolean;
      hidden: boolean;
    };
    scope: {
      id: number;
      name: string;
    };
    name: string;
    type: string;
  }[];
  metrics: {
    config: {
      aggregate_method: string;
      alias: string;
      disabled: boolean;
      function: {
        id: string;
        params: {
          id: string;
          value: number;
        }[];
      }[];
      hidden: boolean;
      interval: number;
      unit: string;
    };
    scope: {
      id: number;
      name: string;
    };
    create_time: number;
    dimensions: string[];
    field_scope: string;
    id: number;
    name: string;
    movable: boolean;
    type: string;
    update_time: number;
  }[];
}

export interface IGroupingRule {
  create_from: 'data' | 'user';
  scope_id: number;
  auto_rules: string[];
  metric_list: {
    field_id: number;
    metric_name: string;
  }[];
  metric_count: number;
  name: string;
}

/** 获取自定义时序列表 rest/v2/custom_metric_report/custom_time_series/ */
export const customTimeSeriesList = CustomReportApi.customTimeSeriesList<
  {
    bk_biz_id?: number;
    page_size: number;
  },
  ICustomTimeSeriesList
>;

/** 获取自定义时序详情 rest/v2/custom_metric_report/custom_time_series_detail/ */
export const customTimeSeriesDetail = CustomReportApi.customTimeSeriesDetail<
  {
    with_metrics?: boolean;
    time_series_group_id: number;
  },
  ICustomTimeSeriesDetail
>;

/** 获取自定义时序字段 rest/v2/custom_metric_report/get_custom_ts_fields/ */
export const getCustomTsFields = CustomReportApi.getCustomTsFields<
  {
    bk_biz_id?: number;
    time_series_group_id: number;
  },
  ICustomTsFields
>;

/** 修改自定义时序字段 rest/v2/custom_metric_report/modify_custom_ts_fields/ */
export const modifyCustomTsFields = CustomReportApi.modifyCustomTsFields<
  {
    time_series_group_id?: number;
    update_fields: {
      scope?: {
        id: number;
        name: string;
      };
      id?: number;
      config?: {
        alias?: string;
        common?: boolean;
        hidden?: boolean;
        interval?: number;
        unit?: string;
        disabled?: boolean;
        function?: {
          id: string;
          params: {
            id: string;
            value: number;
          }[];
        }[];
        aggregate_method?: string;
      };
      dimensions?: string[];
      name?: string;
      type: string;
    }[];
    delete_fields?: {
      scope?: {
        id: number;
        name: string;
      };
      id?: number;
      config?: {
        alias?: string;
        common?: boolean;
        hidden?: boolean;
        interval?: number;
        unit?: string;
        disabled?: boolean;
        function?: {
          id: string;
          params: {
            id: string;
            value: number;
          }[];
        }[];
        aggregate_method?: string;
      };
      dimensions?: string[];
      name?: string;
      type: string;
    }[];
  },
  null
>;

/** 创建或更新分组规则 rest/v2/custom_metric_report/create_or_update_grouping_rule/ */
export const createOrUpdateGroupingRule = CustomReportApi.createOrUpdateGroupingRule<
  {
    bk_biz_id?: number;
    metric_list?: {
      field_id: number;
      metric_name: string;
    }[];
    auto_rules?: string[];
    name?: string;
    scope_id?: number;
    time_series_group_id?: number;
  },
  {
    scope_id: number;
    name: string;
    metric_count: number;
    create_from: 'data' | 'user';
    metric_list: {
      field_id: number;
      metric_name: string;
    }[];
    auto_rules: string[];
  }
>;

/** 获取分组规则列表 rest/v2/custom_metric_report/custom_ts_grouping_rule_list/ */
export const customTsGroupingRuleList = CustomReportApi.customTsGroupingRuleList<
  {
    bk_biz_id?: number;
    time_series_group_id: number;
  },
  IGroupingRule[]
>;

/** 获取最新数据 rest/v2/custom_metric_report/get_custom_time_series_latest_data_by_fields/ */
export const getCustomTimeSeriesLatestDataByFields = CustomReportApi.getCustomTimeSeriesLatestDataByFields<
  {
    metric_list: {
      field_id: number;
      metric_name: string;
    }[];
    result_table_id: string;
  },
  {
    fields_value: Record<string, any>;
    last_time: null | number;
    table_id: string;
  }
>;

/** 预览分组规则 rest/v2/custom_metric_report/preview_grouping_rule/ */
export const previewGroupingRule = CustomReportApi.previewGroupingRule<
  {
    time_series_group_id: number;
    auto_rules: string[];
  },
  {
    auto_metrics: {
      auto_rule: string;
      metrics: string[];
    }[];
    manual_metrics: string[];
  }
>;

/** 修改自定义时序 rest/v2/custom_metric_report/modify_custom_time_series/ */
export const modifyCustomTimeSeries = CustomReportApi.modifyCustomTimeSeries<
  {
    time_series_group_id: number;
    desc?: string;
    name?: string;
    data_label?: string;
  },
  null
>;

/** 导入自定义时序 rest/v2/custom_metric_report/import_custom_time_series_fields/ */
export const importCustomTimeSeriesFields = CustomReportApi.importCustomTimeSeriesFields<
  {
    time_series_group_id: number;
    [key: string]: string | number;
  },
  Record<string, any>
>;

/** 导出自定义时序 rest/v2/custom_metric_report/validate_custom_ts_group_name/ */
export const exportCustomTimeSeriesFields = CustomReportApi.exportCustomTimeSeriesFields<
  {
    time_series_group_id: number;
  },
  Record<string, any>
>;

/** 验证自定义时序名称 rest/v2/custom_metric_report/validate_custom_ts_group_name/ */
export const validateCustomTsGroupName = CustomReportApi.validateCustomTsGroupName<
  {
    name: string;
    time_series_group_id: number;
  },
  {
    result: boolean;
  }
>;

/** 验证自定义时序标签 rest/v2/custom_metric_report/validate_custom_ts_group_label/ */
export const validateCustomTsGroupLabel = CustomReportApi.validateCustomTsGroupLabel<
  {
    data_label: string;
    time_series_group_id?: number;
  },
  boolean
>;

/** 删除分组规则 rest/v2/custom_metric_report/delete_grouping_rule/ */
export const deleteGroupingRule = CustomReportApi.deleteGroupingRule<
  {
    time_series_group_id: number;
    name: string;
  },
  null
>;

/** 获取云区域proxy信息 rest/v2/custom_event_report/proxy_host_info/ */
export const proxyHostInfo = CustomReportApi.proxyHostInfo<
  null,
  {
    bk_cloud_id: number;
    ip: string;
    port: number;
  }[]
>;

export default {
  customTimeSeriesList,
  customTimeSeriesDetail,
  getCustomTsFields,
  modifyCustomTsFields,
  createOrUpdateGroupingRule,
  customTsGroupingRuleList,
  previewGroupingRule,
  getCustomTimeSeriesLatestDataByFields,
  modifyCustomTimeSeries,
  exportCustomTimeSeriesFields,
  validateCustomTsGroupLabel,
  deleteGroupingRule,
};
