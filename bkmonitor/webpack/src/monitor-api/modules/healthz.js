import { request } from '../base';

export const getAlarmConfig = request('GET', 'rest/v1/alarm_config/');
export const updateAlarmConfig = request('POST', 'rest/v1/alarm_config/');

export default {
  getAlarmConfig,
  updateAlarmConfig,
};
