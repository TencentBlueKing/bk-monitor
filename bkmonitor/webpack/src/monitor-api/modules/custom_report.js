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
export const customTimeSeriesList = request('GET', 'rest/v2/custom_metric_report/custom_time_series/');
export const customTimeSeriesDetail = request('GET', 'rest/v2/custom_metric_report/custom_time_series_detail/');
export const validateCustomTsGroupName = request('GET', 'rest/v2/custom_metric_report/validate_custom_ts_group_name/');
export const validateCustomTsGroupLabel = request('GET', 'rest/v2/custom_metric_report/validate_custom_ts_group_label/');
export const createCustomTimeSeries = request('POST', 'rest/v2/custom_metric_report/create_custom_time_series/');
export const modifyCustomTimeSeries = request('POST', 'rest/v2/custom_metric_report/modify_custom_time_series/');
export const deleteCustomTimeSeries = request('POST', 'rest/v2/custom_metric_report/delete_custom_time_series/');
export const addCustomMetric = request('POST', 'rest/v2/custom_metric_report/add_custom_metric/');
export const getCustomTsFields = request('GET', 'rest/v2/custom_metric_report/get_custom_ts_fields/');
export const modifyCustomTsFields = request('POST', 'rest/v2/custom_metric_report/modify_custom_ts_fields/');
export const importCustomTimeSeriesFields = request('POST', 'rest/v2/custom_metric_report/import_custom_time_series_fields/');
export const exportCustomTimeSeriesFields = request('GET', 'rest/v2/custom_metric_report/export_custom_time_series_fields/');
export const createOrUpdateGroupingRule = request('POST', 'rest/v2/custom_metric_report/create_or_update_grouping_rule/');
export const customTsGroupingRuleList = request('GET', 'rest/v2/custom_metric_report/custom_ts_grouping_rule_list/');
export const previewGroupingRule = request('POST', 'rest/v2/custom_metric_report/preview_grouping_rule/');
export const deleteGroupingRule = request('POST', 'rest/v2/custom_metric_report/delete_grouping_rule/');
export const updateGroupingRuleOrder = request('POST', 'rest/v2/custom_metric_report/update_grouping_rule_order/');
export const modifyCustomTsGroupingRuleList = request('POST', 'rest/v2/custom_metric_report/modify_custom_ts_grouping_rule_list/');
export const getCustomTimeSeriesLatestDataByFields = request('POST', 'rest/v2/custom_metric_report/get_custom_time_series_latest_data_by_fields/');
export const modifyCustomTimeSeriesDesc = request('POST', 'rest/v2/custom_metric_report/modify_custom_time_series_desc/');

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
  customTimeSeriesList,
  customTimeSeriesDetail,
  validateCustomTsGroupName,
  validateCustomTsGroupLabel,
  createCustomTimeSeries,
  modifyCustomTimeSeries,
  deleteCustomTimeSeries,
  addCustomMetric,
  getCustomTsFields,
  modifyCustomTsFields,
  importCustomTimeSeriesFields,
  exportCustomTimeSeriesFields,
  createOrUpdateGroupingRule,
  customTsGroupingRuleList,
  previewGroupingRule,
  deleteGroupingRule,
  updateGroupingRuleOrder,
  modifyCustomTsGroupingRuleList,
  getCustomTimeSeriesLatestDataByFields,
  modifyCustomTimeSeriesDesc,
};
