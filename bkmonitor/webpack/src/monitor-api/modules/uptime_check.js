import { request } from '../base';

export const frontPageData = request('POST', 'rest/v2/uptime_check/front_page_data/');
export const getHttpHeaders = request('GET', 'rest/v2/uptime_check/get_http_headers/');
export const getStrategyStatus = request('POST', 'rest/v2/uptime_check/get_strategy_status/');
export const taskDetail = request('GET', 'rest/v2/uptime_check/task_detail/');
export const taskGraphAndMap = request('POST', 'rest/v2/uptime_check/task_graph_and_map/');
export const exportUptimeCheckConf = request('GET', 'rest/v2/uptime_check/export_uptime_check_conf/');
export const exportUptimeCheckNodeConf = request('GET', 'rest/v2/uptime_check/export_uptime_check_node_conf/');
export const fileParse = request('GET', 'rest/v2/uptime_check/import_uptime_check/parse/');
export const fileImportUptimeCheck = request('POST', 'rest/v2/uptime_check/import_uptime_check/');
export const selectUptimeCheckNode = request('GET', 'rest/v2/uptime_check/select_uptime_check_node/');
export const selectCarrierOperator = request('GET', 'rest/v2/uptime_check/select_carrier_operator/');
export const uptimeCheckTargetDetail = request('POST', 'rest/v2/uptime_check/uptime_check_target_detail/');

export default {
  frontPageData,
  getHttpHeaders,
  getStrategyStatus,
  taskDetail,
  taskGraphAndMap,
  exportUptimeCheckConf,
  exportUptimeCheckNodeConf,
  fileParse,
  fileImportUptimeCheck,
  selectUptimeCheckNode,
  selectCarrierOperator,
  uptimeCheckTargetDetail,
};
