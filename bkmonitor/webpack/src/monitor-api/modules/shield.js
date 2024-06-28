import { request } from '../base';

export const shieldList = request('POST', 'rest/v2/shield/shield_list/');
export const frontendShieldList = request('POST', 'rest/v2/shield/frontend_shield_list/');
export const shieldDetail = request('GET', 'rest/v2/shield/shield_detail/');
export const frontendShieldDetail = request('GET', 'rest/v2/shield/frontend_shield_detail/');
export const frontendCloneInfo = request('GET', 'rest/v2/shield/frontend_clone_info/');
export const shieldSnapshot = request('POST', 'rest/v2/shield/shield_snapshot/');
export const addShield = request('POST', 'rest/v2/shield/add_shield/');
export const bulkAddAlertShield = request('POST', 'rest/v2/shield/bulk_add_alert_shield/');
export const editShield = request('POST', 'rest/v2/shield/edit_shield/');
export const disableShield = request('POST', 'rest/v2/shield/disable_shield/');
export const updateFailureShieldContent = request('GET', 'rest/v2/shield/update_failure_shield_content/');

export default {
  shieldList,
  frontendShieldList,
  shieldDetail,
  frontendShieldDetail,
  frontendCloneInfo,
  shieldSnapshot,
  addShield,
  bulkAddAlertShield,
  editShield,
  disableShield,
  updateFailureShieldContent,
};
