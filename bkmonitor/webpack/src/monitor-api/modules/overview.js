import { request } from '../base';

export const monitorInfo = request('GET', 'rest/v2/overview/monitor_info/');
export const search = request('GET', 'rest/v2/overview/search/');
export const getFunctionShortcut = request('POST', 'rest/v2/overview/function_shortcut/');
export const addAccessRecord = request('POST', 'rest/v2/overview/function_shortcut/add_access_record/');
export const getAlarmGraphConfig = request('GET', 'rest/v2/overview/alarm_graph_config/');
export const saveAlarmGraphConfig = request('POST', 'rest/v2/overview/alarm_graph_config/');
export const deleteAlarmGraphConfig = request('POST', 'rest/v2/overview/alarm_graph_config/delete/');
export const saveAlarmGraphBizIndex = request('POST', 'rest/v2/overview/alarm_graph_config/save_biz_index/');

export default {
  monitorInfo,
  search,
  getFunctionShortcut,
  addAccessRecord,
  getAlarmGraphConfig,
  saveAlarmGraphConfig,
  deleteAlarmGraphConfig,
  saveAlarmGraphBizIndex,
};

