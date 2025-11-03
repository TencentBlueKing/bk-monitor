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
import { request } from '../base';

export const traceChats = request('GET', 'apm/trace_api/trace_query/trace_charts/');
export const traceOptions = request('GET', 'apm/trace_api/trace_query/trace_options/');
export const listTrace = request('POST', 'apm/trace_api/trace_query/list_traces/');
export const listSpan = request('POST', 'apm/trace_api/trace_query/list_spans/');
export const listStandardFilterFields = request('GET', 'apm/trace_api/trace_query/standard_fields/');
export const listFlattenTrace = request('POST', 'apm/trace_api/trace_query/list_flatten_traces/');
export const listFlattenSpan = request('POST', 'apm/trace_api/trace_query/list_flatten_spans/');
export const traceStatistics = request('POST', 'apm/trace_api/trace_query/trace_statistics/');
export const traceListById = request('POST', 'apm/trace_api/trace_query/trace_list_by_id/');
export const traceListByHostInstance = request('POST', 'apm/trace_api/trace_query/trace_list_by_host_instance/');
export const traceDetail = request('POST', 'apm/trace_api/trace_query/trace_detail/');
export const spanDetail = request('POST', 'apm/trace_api/trace_query/span_detail/');
export const traceDiagram = request('POST', 'apm/trace_api/trace_query/trace_diagram/');
export const listOptionValues = request('POST', 'apm/trace_api/trace_query/list_option_values/');
export const getFieldOptionValues = request('POST', 'apm/trace_api/trace_query/get_field_option_values/');
export const listSpanStatistics = request('POST', 'apm/trace_api/trace_query/list_span_statistics/');
export const listServiceStatistics = request('POST', 'apm/trace_api/trace_query/list_service_statistics/');
export const listTraceViewConfig = request('GET', 'apm/trace_api/trace_query/view_config/');
export const getFieldsOptionValues = request('POST', 'apm/trace_api/trace_query/get_fields_option_values/');
export const applyTraceComparison = request('POST', 'apm/trace_api/trace_query/apply_trace_comparison/');
export const deleteTraceComparison = request('POST', 'apm/trace_api/trace_query/delete_trace_comparison/');
export const listTraceComparison = request('POST', 'apm/trace_api/trace_query/list_trace_comparison/');
export const listSpanHostInstances = request('GET', 'apm/trace_api/trace_query/list_span_host_instances/');
export const traceDownloadTopK = request('POST', 'apm/trace_api/trace_query/download_topk/');
export const traceFieldsTopK = request('POST', 'apm/trace_api/trace_query/fields_topk/');
export const traceFieldStatisticsInfo = request('POST', 'apm/trace_api/trace_query/field_statistics_info/');
export const traceFieldStatisticsGraph = request('POST', 'apm/trace_api/trace_query/field_statistics_graph/');
export const traceGenerateQueryString = request('POST', 'apm/trace_api/trace_query/generate_query_string/');

export default {
  traceChats,
  traceOptions,
  listTrace,
  listSpan,
  listStandardFilterFields,
  listFlattenTrace,
  listFlattenSpan,
  traceStatistics,
  traceListById,
  traceListByHostInstance,
  traceDetail,
  spanDetail,
  traceDiagram,
  listOptionValues,
  getFieldOptionValues,
  listSpanStatistics,
  listServiceStatistics,
  listTraceViewConfig,
  getFieldsOptionValues,
  applyTraceComparison,
  deleteTraceComparison,
  listTraceComparison,
  listSpanHostInstances,
  traceDownloadTopK,
  traceFieldsTopK,
  traceFieldStatisticsInfo,
  traceFieldStatisticsGraph,
  traceGenerateQueryString,
};
