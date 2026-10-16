import { request } from '../base';

export const getActiveProfilingMetaConfig = request(
  'GET',
  'apm/profile_api/active_collection/active_profiling_meta_config/'
);
export const enableActiveCollection = request('POST', 'apm/profile_api/active_collection/enable/');
export const previewProcesses = request('POST', 'apm/profile_api/active_collection/processes/preview/');
export const listTasks = request('GET', 'apm/profile_api/active_collection/tasks/');
export const submitTask = request('POST', 'apm/profile_api/active_collection/tasks/');
export const editTask = request('POST', 'apm/profile_api/active_collection/tasks/edit/');
export const deleteTask = request('POST', 'apm/profile_api/active_collection/tasks/delete/');
export const switchTask = request('POST', 'apm/profile_api/active_collection/tasks/switch/');
export const queryHosts = request('POST', 'apm/profile_api/active_collection/hosts/query/');
export const listExecutions = request('POST', 'apm/profile_api/active_collection/executions/list/');
export const queryTopK = request('GET', 'apm/profile_api/active_collection/topk/');
export const getExecutionDetail = request('POST', 'apm/profile_api/active_collection/executions/detail/');
export const cancelExecution = request('POST', 'apm/profile_api/active_collection/executions/cancel/');
export const queryResults = request('POST', 'apm/profile_api/active_collection/results/query/');
export const queryResultDataTypes = request('POST', 'apm/profile_api/active_collection/results/data_types/');
export const exportResults = request('POST', 'apm/profile_api/active_collection/results/export/');

export default {
  getActiveProfilingMetaConfig,
  enableActiveCollection,
  previewProcesses,
  listTasks,
  submitTask,
  editTask,
  deleteTask,
  switchTask,
  queryHosts,
  listExecutions,
  queryTopK,
  getExecutionDetail,
  cancelExecution,
  queryResults,
  queryResultDataTypes,
  exportResults
};
