import { request } from '../base';

export const test = request('GET', 'rest/v2/grafana/');
export const bkLogSearchQuery = request('POST', 'query-api/rest/v2/grafana/bk_log_search/grafana/query/');
export const bkLogSearchMetric = request('GET', 'rest/v2/grafana/bk_log_search/grafana/metric/');
export const bkLogSearchDimension = request('GET', 'query-api/rest/v2/grafana/bk_log_search/grafana/dimension/');
export const bkLogSearchTargetTree = request('GET', 'rest/v2/grafana/bk_log_search/grafana/target_tree/');
export const bkLogSearchQueryLog = request('POST', 'query-api/rest/v2/grafana/bk_log_search/grafana/query_log/');
export const bkLogSearchGetVariableField = request('GET', 'rest/v2/grafana/bk_log_search/grafana/get_variable_field/');
export const bkLogSearchGetVariableValue = request('POST', 'query-api/rest/v2/grafana/bk_log_search/grafana/get_variable_value/');
export const getLabel = request('GET', 'rest/v2/grafana/get_label/');
export const getTopoTree = request('GET', 'rest/v2/grafana/topo_tree/');
export const getDimensionValues = request('GET', 'rest/v2/grafana/get_dimension_values/');
export const getMetricListV2 = request('POST', 'rest/v2/grafana/get_metric_list/');
export const getDataSourceConfig = request('GET', 'rest/v2/grafana/get_data_source_config/');
export const getVariableValue = request('POST', 'query-api/rest/v2/grafana/get_variable_value/');
export const getVariableField = request('GET', 'rest/v2/grafana/get_variable_field/');
export const timeSeriesMetric = request('POST', 'rest/v2/grafana/time_series/metric/');
export const timeSeriesMetricLevel = request('POST', 'rest/v2/grafana/time_series/metric_level/');
export const logQuery = request('POST', 'query-api/rest/v2/grafana/log/query/');
export const getDashboardList = request('GET', 'rest/v2/grafana/dashboards/');
export const setDefaultDashboard = request('POST', 'rest/v2/grafana/set_default_dashboard/');
export const getDefaultDashboard = request('GET', 'rest/v2/grafana/get_default_dashboard/');
export const getDirectoryTree = request('GET', 'rest/v2/grafana/get_directory_tree/');
export const createDashboardOrFolder = request('POST', 'rest/v2/grafana/create_dashboard_or_folder/');
export const deleteDashboard = request('DELETE', 'rest/v2/grafana/delete_dashboard/');
export const starDashboard = request('POST', 'rest/v2/grafana/star_dashboard/');
export const unstarDashboard = request('DELETE', 'rest/v2/grafana/unstar_dashboard/');
export const deleteFolder = request('DELETE', 'rest/v2/grafana/delete_folder/');
export const renameFolder = request('PUT', 'rest/v2/grafana/rename_folder/');
export const quickImportDashboard = request('POST', 'rest/v2/grafana/quick_import_dashboard/');
export const saveToDashboard = request('POST', 'rest/v2/grafana/save_to_dashboard/');
export const getFunctions = request('GET', 'rest/v2/grafana/time_series/functions/');
export const graphUnifyQuery = request('POST', 'query-api/rest/v2/grafana/time_series/unify_query/');
export const unifyQueryRaw = request('POST', 'query-api/rest/v2/grafana/time_series/unify_query_raw/');
export const dimensionUnifyQuery = request('POST', 'rest/v2/grafana/time_series/dimension_query/');
export const dimensionCountUnifyQuery = request('POST', 'rest/v2/grafana/time_series/dimension_count/');
export const queryConfigToPromql = request('POST', 'rest/v2/grafana/query_config_to_promql/');
export const promqlToQueryConfig = request('POST', 'rest/v2/grafana/promql_to_query_config/');
export const graphPromqlQuery = request('POST', 'query-api/rest/v2/grafana/graph_promql_query/');
export const dimensionPromqlQuery = request('POST', 'query-api/rest/v2/grafana/dimension_promql_query/');
export const convertGrafanaPromqlDashboard = request('POST', 'rest/v2/grafana/convert_grafana_promql_dashboard/');
export const graphTraceQuery = request('POST', 'rest/v2/grafana/time_series/unify_trace_query/');
export const updateMetricListByBiz = request('POST', 'rest/v2/grafana/update_metric_list_by_biz/');
export const queryAsyncTaskResult = request('GET', 'rest/v2/grafana/query_async_task_result/');
export const addCustomMetric = request('POST', 'rest/v2/grafana/add_custom_metric/');

export default {
  test,
  bkLogSearchQuery,
  bkLogSearchMetric,
  bkLogSearchDimension,
  bkLogSearchTargetTree,
  bkLogSearchQueryLog,
  bkLogSearchGetVariableField,
  bkLogSearchGetVariableValue,
  getLabel,
  getTopoTree,
  getDimensionValues,
  getMetricListV2,
  getDataSourceConfig,
  getVariableValue,
  getVariableField,
  timeSeriesMetric,
  timeSeriesMetricLevel,
  logQuery,
  getDashboardList,
  setDefaultDashboard,
  getDefaultDashboard,
  getDirectoryTree,
  createDashboardOrFolder,
  deleteDashboard,
  starDashboard,
  unstarDashboard,
  deleteFolder,
  renameFolder,
  quickImportDashboard,
  saveToDashboard,
  getFunctions,
  graphUnifyQuery,
  unifyQueryRaw,
  dimensionUnifyQuery,
  dimensionCountUnifyQuery,
  queryConfigToPromql,
  promqlToQueryConfig,
  graphPromqlQuery,
  dimensionPromqlQuery,
  convertGrafanaPromqlDashboard,
  graphTraceQuery,
  updateMetricListByBiz,
  queryAsyncTaskResult,
  addCustomMetric
};
