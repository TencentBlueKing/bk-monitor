import { request } from '../base';

export const errorListByTraceIds = request('POST', 'apm/metric/metric_event/error_list_by_trace_ids/');
export const serviceList = request('POST', 'apm/metric/metric/service_list/');
export const serviceInstances = request('POST', 'apm/metric/metric/service_instances/');
export const errorList = request('POST', 'apm/metric/metric/error_list/');
export const endpointList = request('POST', 'apm/metric/metric/endpoint_list/');
export const hostInstanceDetailList = request('POST', 'apm/metric/metric/host_instance_detail_list/');
export const hostDetail = request('POST', 'apm/metric/metric/host_instance_detail/');
export const apdexQuery = request('GET', 'apm/metric/metric/apdex_query/');
export const alertQuery = request('GET', 'apm/metric/metric/alert_query/');
export const unifyQuery = request('POST', 'apm/metric/metric/unify_query/');
export const dynamicUnifyQuery = request('POST', 'apm/metric/metric/dynamic_unify_query/');
export const serviceListAsync = request('POST', 'apm/metric/metric/service_list_async/');
export const topNQuery = request('POST', 'apm/metric/metric/top_n_query/');
export const instanceList = request('POST', 'apm/metric/metric/instance_list/');
export const collectService = request('POST', 'apm/metric/metric/collect_service/');
export const endpointDetailList = request('POST', 'apm/metric/metric/endpoint_detail_list/');
export const exceptionDetailList = request('POST', 'apm/metric/metric/exception_detail_list/');
export const serviceQueryException = request('POST', 'apm/metric/metric/service_query_exception/');
export const metricDetailStatistics = request('GET', 'apm/metric/metric/metric_statistics/');
export const getFieldOptionValues = request('POST', 'apm/metric/metric/get_field_option_values/');
export const calculateByRange = request('POST', 'apm/metric/metric/calculate_by_range/');
export const queryDimensionsByLimit = request('POST', 'apm/metric/metric/query_dimensions_by_limit/');

export default {
  errorListByTraceIds,
  serviceList,
  serviceInstances,
  errorList,
  endpointList,
  hostInstanceDetailList,
  hostDetail,
  apdexQuery,
  alertQuery,
  unifyQuery,
  dynamicUnifyQuery,
  serviceListAsync,
  topNQuery,
  instanceList,
  collectService,
  endpointDetailList,
  exceptionDetailList,
  serviceQueryException,
  metricDetailStatistics,
  getFieldOptionValues,
  calculateByRange,
  queryDimensionsByLimit,
};
