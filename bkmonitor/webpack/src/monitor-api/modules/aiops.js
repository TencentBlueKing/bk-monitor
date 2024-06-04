import { request } from '../base';

export const fetchAiSetting = request('GET', 'rest/v2/ai_setting/fetch_ai_setting/');
export const saveAiSetting = request('POST', 'rest/v2/ai_setting/save_ai_setting/');
export const hostIntelligenAnomaly = request('POST', 'rest/v2/host_monitor/host_intelligen_anomaly/');
export const hostIntelligenAnomalyRange = request('POST', 'rest/v2/host_monitor/host_intelligen_anomaly_range/');

export default {
  fetchAiSetting,
  saveAiSetting,
  hostIntelligenAnomaly,
  hostIntelligenAnomalyRange,
};
