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
  name: string;
  protocol: string;
  scenario: string;
  scenario_display: string[];
  table_id: string;
  target: any[];
  time_series_group_id: number;
  update_time: string;
  update_user: string;
}

interface ICustomTimeSeriesList {
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
  total: number;
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
    page_size: number;
    bk_biz_id?: number;
  },
  ICustomTimeSeriesList
>;

export const customTimeSeriesDetail = CustomReportApi.customTimeSeriesDetail<
  {
    time_series_group_id: number;
    bk_biz_id?: number;
  },
  ICustomTimeSeriesDetail
>;

export const getCustomTsFields = CustomReportApi.getCustomTsFields<
  {
    time_series_group_id: number;
    bk_biz_id?: number;
  },
  ICustomTsFields
>;

export const modifyCustomTsFields = CustomReportApi.modifyCustomTsFields<
  {
    bk_biz_id: number;
    time_series_group_id: number;
    update_fields: {
      common: boolean;
      name: string;
      type: 'metric' | 'dimension';
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
    time_series_group_id: number;
    bk_biz_id?: number;
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
    last_time: number | null;
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
