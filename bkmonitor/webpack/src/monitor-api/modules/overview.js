import { request } from '../base';

export const alarmRank = request('GET', 'rest/v2/overview/alarm_rank/');
export const alarmCountInfo = request('GET', 'rest/v2/overview/alarm_count_info/');
export const monitorInfo = request('GET', 'rest/v2/overview/monitor_info/');

export default {
  alarmRank,
  alarmCountInfo,
  monitorInfo,
};
