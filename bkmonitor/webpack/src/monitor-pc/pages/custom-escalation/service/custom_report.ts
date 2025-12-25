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

interface ICustomTimeSeriesDetail {
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

interface ICustomTimeSeriesList {
  total: number;
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

interface ICustomTsFields {
  dimensions: {
    common: boolean;
    create_time: number;
    description: string;
    disabled: boolean;
    hidden: boolean;
    name: string;
    type: string;
    update_time: number;
  }[];
  metrics: {
    aggregate_method: string;
    create_time: number;
    description: string;
    dimensions: string[];
    disabled: boolean;
    function: Record<string, any>;
    hidden: boolean;
    interval: number;
    label: string[];
    name: string;
    type: string;
    unit: string;
    update_time: number;
  }[];
}

export const customTimeSeriesList = CustomReportApi.customTimeSeriesList<
  {
    bk_biz_id?: number;
    page_size: number;
  },
  ICustomTimeSeriesList
>;

export const customTimeSeriesDetail = CustomReportApi.customTimeSeriesDetail<
  {
    bk_biz_id?: number;
    time_series_group_id: number;
  },
  ICustomTimeSeriesDetail
>;

export const getCustomTsFields = CustomReportApi.getCustomTsFields<
  {
    bk_biz_id?: number;
    time_series_group_id: number;
  },
  ICustomTsFields
>;

export const modifyCustomTsFields = CustomReportApi.modifyCustomTsFields<
  {
    bk_biz_id?: number;
    time_series_group_id: number;
    update_fields: {
      common?: boolean;
      config: {
        alias: string;
      };
      id: number;
      name: string;
      scope: {
        id: number;
        name: string;
      };
      type: 'dimension' | 'metric';
    }[];
  },
  null
>;

export const createOrUpdateGroupingRule = CustomReportApi.createOrUpdateGroupingRule<
  {
    bk_biz_id: number;
    manual_list: string[];
    name: string;
    time_series_group_id: number;
  },
  null
>;

export const customTsGroupingRuleList = CustomReportApi.customTsGroupingRuleList<
  {
    bk_biz_id?: number;
    time_series_group_id: number;
  },
  {
    auto_rules: string[];
    manual_list: string[];
    metric_count: number;
    name: string;
  }[]
>;

export const getCustomTimeSeriesLatestDataByFields = CustomReportApi.getCustomTimeSeriesLatestDataByFields<
  {
    bk_biz_id: number;
    fields_list: string[];
    result_table_id: string;
  },
  {
    fields_value: Record<string, any>;
    last_time: null | number;
    table_id: string;
  }
>;

export default {
  customTimeSeriesList,
  customTimeSeriesDetail,
  getCustomTsFields,
  modifyCustomTsFields,
  createOrUpdateGroupingRule,
  customTsGroupingRuleList,
  getCustomTimeSeriesLatestDataByFields,
};
