import { request } from '../base';

export const alertStatus = request('GET', 'rest/v2/datalink_status/alert_status/');
export const updateAlertUserGroups = request('POST', 'rest/v2/datalink_status/update_alert_user_groups/');
export const collectingTargetStatus = request('GET', 'rest/v2/datalink_status/collecting_target_status/');
export const transferCountSeries = request('GET', 'rest/v2/datalink_status/transfer_count_series/');
export const transferLatestMsg = request('GET', 'rest/v2/datalink_status/transfer_latest_msg/');
export const storageStatus = request('GET', 'rest/v2/datalink_status/storage_status/');

export default {
  alertStatus,
  updateAlertUserGroups,
  collectingTargetStatus,
  transferCountSeries,
  transferLatestMsg,
  storageStatus,
};
