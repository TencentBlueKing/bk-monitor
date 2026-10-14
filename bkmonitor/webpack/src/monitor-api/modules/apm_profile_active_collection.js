import { request } from '../base';

const prefix = 'apm/profile_api/active_collection/';
export const metaConfig = request('GET', `${prefix}active_profiling_meta_config/`);
export const previewProcesses = request('POST', `${prefix}processes/preview/`);
export const listTasks = request('GET', `${prefix}tasks/`);
export const createTask = request('POST', `${prefix}tasks/`);
export const editTask = request('POST', `${prefix}tasks/edit/`);
export const deleteTask = request('POST', `${prefix}tasks/delete/`);
export const switchTask = request('POST', `${prefix}tasks/switch/`);

export default { metaConfig, previewProcesses, listTasks, createTask, editTask, deleteTask, switchTask };
