import { request } from '../base';

const prefix = 'apm/profile_api/active_collection/';
export const metaConfig = request('GET', `${prefix}active_profiling_meta_config/`);
export const previewProcesses = request('POST', `${prefix}processes/preview/`);
export const listTasks = request('GET', `${prefix}tasks/`);
export const createTask = request('POST', `${prefix}tasks/`);
export const editTask = request('POST', `${prefix}tasks/edit/`);
export const deleteTask = request('POST', `${prefix}tasks/delete/`);
export const switchTask = request('POST', `${prefix}tasks/switch/`);
export const listExecutions = request('POST', `${prefix}executions/list/`);
export const executionDetail = request('POST', `${prefix}executions/detail/`);
export const cancelExecution = request('POST', `${prefix}executions/cancel/`);
export const collectionTopk = request('GET', `${prefix}topk/`);
export const queryHosts = request('POST', `${prefix}hosts/query/`);
export const resultDataTypes = request('POST', `${prefix}results/data_types/`);
export const queryResult = request('POST', `${prefix}results/query/`);
export const exportResult = request('POST', `${prefix}results/export/`);
export const executionsRename = request('POST', `${prefix}executions/rename/`);

export default { metaConfig, previewProcesses, listTasks, createTask, editTask, deleteTask, switchTask, listExecutions, executionDetail, cancelExecution, collectionTopk, queryHosts, resultDataTypes, queryResult, exportResult, executionsRename };
