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

export const metaConfigInfo = request('GET', 'apm/meta/meta_info/meta_config_info/');
export const metaInstrumentGuides = request('POST', 'apm/meta/meta_info/meta_instrument_guides/');
export const pushUrl = request('GET', 'apm/meta/meta_info/push_url/');
export const listEsClusterGroups = request('GET', 'apm/meta/meta_info/list_cluster_groups/');
export const listApplicationInfo = request('GET', 'apm/meta/application/list_application_info/');
export const listApplication = request('POST', 'apm/meta/application/list_application/');
export const metricInfo = request('GET', 'apm/meta/application/{pk}/metric_info/');
export const dimensionData = request('POST', 'apm/meta/application/{pk}/dimension_data/');
export const modifyMetric = request('POST', 'apm/meta/application/{pk}/modify_metric/');
export const applicationInfo = request('GET', 'apm/meta/application/{pk}/application_info/');
export const applicationInfoByAppName = request('GET', 'apm/meta/application/application_info_by_app_name/');
export const listApplicationAsync = request('POST', 'apm/meta/application/list_application_async/');
export const instanceDiscoverKeys = request('POST', 'apm/meta/application/instance_discover_keys/');
export const serviceDetail = request('POST', 'apm/meta/application/service_detail/');
export const endpointDetail = request('POST', 'apm/meta/application/endpoint_detail/');
export const serviceList = request('POST', 'apm/meta/application/service_list/');
export const queryExceptionEvent = request('POST', 'apm/meta/application/query_exception_event/');
export const queryExceptionDetailEvent = request('POST', 'apm/meta/application/query_exception_detail_event/');
export const queryExceptionEndpoint = request('POST', 'apm/meta/application/query_exception_endpoint/');
export const queryExceptionTypeGraph = request('POST', 'apm/meta/application/query_exception_type_graph/');
export const queryEndpointStatistics = request('POST', 'apm/meta/application/query_endpoint_statistics/');
export const queryBkDataToken = request('GET', 'apm/meta/application/{pk}/query_bk_data_token/');
export const checkDuplicateName = request('GET', 'apm/meta/application/check_duplicate_app_name/');
export const indicesInfo = request('GET', 'apm/meta/application/{pk}/indices_info/');
export const createApplication = request('POST', 'apm/meta/application/create_application/');
export const deleteApplication = request('POST', 'apm/meta/application/delete_application/');
export const setup = request('POST', 'apm/meta/application/setup/');
export const samplingOptions = request('GET', 'apm/meta/application/sampling_options/');
export const start = request('POST', 'apm/meta/application/start/');
export const stop = request('POST', 'apm/meta/application/stop/');
export const noDataStrategyInfo = request('POST', 'apm/meta/application/nodata_strategy_info/');
export const noDataStrategyEnable = request('POST', 'apm/meta/application/nodata_strategy_enable/');
export const noDataStrategyDisable = request('POST', 'apm/meta/application/nodata_strategy_disable/');
export const dataViewConfig = request('POST', 'apm/meta/application/{pk}/data_view_config/');
export const dataHistogram = request('POST', 'apm/meta/application/{pk}/data_histogram/');
export const dataSampling = request('POST', 'apm/meta/application/{pk}/data_sampling/');
export const dataStatus = request('GET', 'apm/meta/application/{pk}/data_status/');
export const storageInfo = request('POST', 'apm/meta/application/{pk}/storage_info/');
export const storageFieldInfo = request('POST', 'apm/meta/application/{pk}/storage_field_info/');
export const storageStatus = request('GET', 'apm/meta/application/{pk}/storage_status/');
export const customServiceList = request('GET', 'apm/meta/application/custom_service_list/');
export const customServiceConfig = request('POST', 'apm/meta/application/custom_service_config/');
export const deleteCustomSerivice = request('POST', 'apm/meta/application/delete_custom_service/');
export const customServiceMatchList = request('POST', 'apm/meta/application/custom_service_match_list/');
export const customServiceDataView = request('POST', 'apm/meta/application/{pk}/custom_service_data_view_config/');
export const customServiceDataSource = request('POST', 'apm/meta/application/custom_service_url_list/');
export const getDataEncoding = request('GET', 'apm/meta/application/data_encoding/');
export const simpleServiceList = request('POST', 'apm/meta/application/simple_service_list/');

export default {
  metaConfigInfo,
  metaInstrumentGuides,
  pushUrl,
  listEsClusterGroups,
  listApplicationInfo,
  listApplication,
  metricInfo,
  dimensionData,
  modifyMetric,
  applicationInfo,
  applicationInfoByAppName,
  listApplicationAsync,
  instanceDiscoverKeys,
  serviceDetail,
  endpointDetail,
  serviceList,
  queryExceptionEvent,
  queryExceptionDetailEvent,
  queryExceptionEndpoint,
  queryExceptionTypeGraph,
  queryEndpointStatistics,
  queryBkDataToken,
  checkDuplicateName,
  indicesInfo,
  createApplication,
  deleteApplication,
  setup,
  samplingOptions,
  start,
  stop,
  noDataStrategyInfo,
  noDataStrategyEnable,
  noDataStrategyDisable,
  dataViewConfig,
  dataHistogram,
  dataSampling,
  storageInfo,
  storageFieldInfo,
  storageStatus,
  customServiceList,
  customServiceConfig,
  deleteCustomSerivice,
  customServiceMatchList,
  customServiceDataView,
  customServiceDataSource,
  getDataEncoding,
  simpleServiceList,
};
