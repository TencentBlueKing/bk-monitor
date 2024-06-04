import { request } from '../base';

export const proxyHostInfo = request('GET', 'rest/v2/custom_event_report/proxy_host_info/');
export const queryCustomEventGroup = request('GET', 'rest/v2/custom_event_report/query_custom_event_group/');
export const getCustomEventGroup = request('GET', 'rest/v2/custom_event_report/get_custom_event_group/');
export const validateCustomEventGroupName = request('GET', 'rest/v2/custom_event_report/validate_custom_event_group_name/');
export const validateCustomEventGroupLabel = request('GET', 'rest/v2/custom_event_report/validate_custom_event_group_label/');
export const createCustomEventGroup = request('POST', 'rest/v2/custom_event_report/create_custom_event_group/');
export const modifyCustomEventGroup = request('POST', 'rest/v2/custom_event_report/modify_custom_event_group/');
export const deleteCustomEventGroup = request('POST', 'rest/v2/custom_event_report/delete_custom_event_group/');
export const queryCustomEventTarget = request('GET', 'rest/v2/custom_event_report/query_custom_event_target/');
export const getCustomTimeSeriesLatestDataByFields = request('POST', 'rest/v2/custom_metric_report/get_custom_time_series_latest_data_by_fields/');
export const customTimeSeriesList = request('GET', 'rest/v2/custom_metric_report/custom_time_series/');
export const customTimeSeriesDetail = request('GET', 'rest/v2/custom_metric_report/custom_time_series_detail/');
export const customTsGroupingRuleList = request('GET', 'rest/v2/custom_metric_report/custom_ts_grouping_rule_list/');
export const validateCustomTsGroupName = request('GET', 'rest/v2/custom_metric_report/validate_custom_ts_group_name/');
export const validateCustomTsGroupLabel = request('GET', 'rest/v2/custom_metric_report/validate_custom_ts_group_label/');
export const createCustomTimeSeries = request('POST', 'rest/v2/custom_metric_report/create_custom_time_series/');
export const modifyCustomTimeSeries = request('POST', 'rest/v2/custom_metric_report/modify_custom_time_series/');
export const createOrUpdateGroupingRule = request('POST', 'rest/v2/custom_metric_report/create_or_update_grouping_rule/');
export const groupCustomTsItem = request('POST', 'rest/v2/custom_metric_report/group_custom_ts_item/');
export const modifyCustomTsGroupingRuleList = request('POST', 'rest/v2/custom_metric_report/modify_custom_ts_grouping_rule_list/');
export const deleteCustomTimeSeries = request('POST', 'rest/v2/custom_metric_report/delete_custom_time_series/');
export const addCustomMetric = request('POST', 'rest/v2/custom_metric_report/add_custom_metric/');

export default {
  proxyHostInfo,
  queryCustomEventGroup,
  getCustomEventGroup,
  validateCustomEventGroupName,
  validateCustomEventGroupLabel,
  createCustomEventGroup,
  modifyCustomEventGroup,
  deleteCustomEventGroup,
  queryCustomEventTarget,
  getCustomTimeSeriesLatestDataByFields,
  customTimeSeriesList,
  customTimeSeriesDetail,
  customTsGroupingRuleList,
  validateCustomTsGroupName,
  validateCustomTsGroupLabel,
  createCustomTimeSeries,
  modifyCustomTimeSeries,
  createOrUpdateGroupingRule,
  groupCustomTsItem,
  modifyCustomTsGroupingRuleList,
  deleteCustomTimeSeries,
  addCustomMetric,
};
