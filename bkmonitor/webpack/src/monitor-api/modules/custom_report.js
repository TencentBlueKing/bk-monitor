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
export const modifyCustomTimeSeriesDesc = request('POST', 'rest/v2/custom_metric_report/modify_custom_time_series_desc/');
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
  modifyCustomTimeSeriesDesc,
  createOrUpdateGroupingRule,
  groupCustomTsItem,
  modifyCustomTsGroupingRuleList,
  deleteCustomTimeSeries,
  addCustomMetric,
};
