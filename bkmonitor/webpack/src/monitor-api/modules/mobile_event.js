import { request } from '../base';

export const getAlarmDetail = request('GET', 'rest/v1/event/get_alarm_detail/');
export const getEventDetail = request('GET', 'rest/v1/event/get_event_detail/');
export const getEventGraphView = request('GET', 'rest/v1/event/get_event_graph_view/');
export const quickShield = request('POST', 'rest/v1/event/quick_shield/');
export const getEventList = request('GET', 'rest/v1/event/get_event_list/');
export const ackEvent = request('POST', 'rest/v1/event/ack_event/');
export const quickAlertShield = request('GET', 'rest/v1/event/alert/quick_shield/');
export const quickAlertAck = request('GET', 'rest/v1/event/alert/quick_ack/');

export default {
  getAlarmDetail,
  getEventDetail,
  getEventGraphView,
  quickShield,
  getEventList,
  ackEvent,
  quickAlertShield,
  quickAlertAck,
};
