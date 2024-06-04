import { request } from '../base';

export const listEvent = request('POST', 'rest/v2/event_center/list_event/');
export const strategySnapshot = request('GET', 'rest/v2/event_center/strategy_snapshot/');
export const listAlertNotice = request('GET', 'rest/v2/event_center/list_alert_notice/');
export const detailAlertNotice = request('GET', 'rest/v2/event_center/detail_alert_notice/');
export const ackEvent = request('POST', 'rest/v2/event_center/ack_event/');
export const getSolution = request('GET', 'rest/v2/event_center/get_solution/');
export const saveSolution = request('POST', 'rest/v2/event_center/save_solution/');
export const listEventLog = request('POST', 'rest/v2/event_center/event_log/');
export const listSearchItem = request('POST', 'rest/v2/event_center/list_search_item/');
export const listConvergeLog = request('GET', 'rest/v2/event_center/list_converge_log/');
export const stackedChart = request('POST', 'rest/v2/event_center/stacked_chart/');
export const shieldSnapshot = request('GET', 'rest/v2/event_center/shield_snapshot/');
export const listIndexByHost = request('POST', 'rest/v2/event_center/list_index_by_host/');
export const isHostExistsIndex = request('POST', 'rest/v2/event_center/is_host_exists_index/');
export const graphPoint = request('POST', 'rest/v2/event_center/graph_point/');

export default {
  listEvent,
  strategySnapshot,
  listAlertNotice,
  detailAlertNotice,
  ackEvent,
  getSolution,
  saveSolution,
  listEventLog,
  listSearchItem,
  listConvergeLog,
  stackedChart,
  shieldSnapshot,
  listIndexByHost,
  isHostExistsIndex,
  graphPoint,
};
