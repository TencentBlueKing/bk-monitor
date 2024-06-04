import { request } from '../base';

export const traceChats = request('GET', 'apm/trace_api/trace_query/trace_charts/');
export const traceOptions = request('GET', 'apm/trace_api/trace_query/trace_options/');
export const listTrace = request('POST', 'apm/trace_api/trace_query/list_traces/');
export const listSpan = request('POST', 'apm/trace_api/trace_query/list_spans/');
export const listStandardFilterFields = request('GET', 'apm/trace_api/trace_query/standard_fields/');
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
export const applyTraceComparison = request('POST', 'apm/trace_api/trace_query/apply_trace_comparison/');
export const deleteTraceComparison = request('POST', 'apm/trace_api/trace_query/delete_trace_comparison/');
export const listTraceComparison = request('POST', 'apm/trace_api/trace_query/list_trace_comparison/');
export const listSpanHostInstances = request('GET', 'apm/trace_api/trace_query/list_span_host_instances/');

export default {
  traceChats,
  traceOptions,
  listTrace,
  listSpan,
  listStandardFilterFields,
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
  applyTraceComparison,
  deleteTraceComparison,
  listTraceComparison,
  listSpanHostInstances,
};
