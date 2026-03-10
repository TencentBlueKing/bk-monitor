import { request } from '../base';

export const getCustomTsFields = request('GET', 'apm/custom_metric/custom_metric/get_custom_ts_fields/');
export const modifyCustomTsFields = request('POST', 'apm/custom_metric/custom_metric/modify_custom_ts_fields/');
export const customTsGroupingRuleList = request('GET', 'apm/custom_metric/custom_metric/custom_ts_grouping_rule_list/');
export const createOrUpdateGroupingRule = request('POST', 'apm/custom_metric/custom_metric/create_or_update_grouping_rule/');
export const previewGroupingRule = request('POST', 'apm/custom_metric/custom_metric/preview_grouping_rule/');
export const deleteGroupingRule = request('POST', 'apm/custom_metric/custom_metric/delete_grouping_rule/');
export const importCustomTimeSeriesFields = request('POST', 'apm/custom_metric/custom_metric/import_custom_time_series_fields/');
export const exportCustomTimeSeriesFields = request('GET', 'apm/custom_metric/custom_metric/export_custom_time_series_fields/');

export default {
  getCustomTsFields,
  modifyCustomTsFields,
  customTsGroupingRuleList,
  createOrUpdateGroupingRule,
  previewGroupingRule,
  deleteGroupingRule,
  importCustomTimeSeriesFields,
  exportCustomTimeSeriesFields,
};
