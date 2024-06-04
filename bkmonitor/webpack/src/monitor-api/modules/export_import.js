import { request } from '../base';

export const getAllConfigList = request('GET', 'rest/v2/export_import/get_all_config_list/');
export const exportPackage = request('POST', 'rest/v2/export_import/export_package/');
export const historyList = request('GET', 'rest/v2/export_import/history_list/');
export const historyDetail = request('GET', 'rest/v2/export_import/history_detail/');
export const uploadPackage = request('POST', 'rest/v2/export_import/upload_package/');
export const importConfig = request('POST', 'rest/v2/export_import/import_config/');
export const addMonitorTarget = request('POST', 'rest/v2/export_import/add_monitor_target/');

export default {
  getAllConfigList,
  exportPackage,
  historyList,
  historyDetail,
  uploadPackage,
  importConfig,
  addMonitorTarget,
};
