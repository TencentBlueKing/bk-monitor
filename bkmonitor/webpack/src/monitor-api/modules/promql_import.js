import { request } from '../base';

export const createMappingConfig = request('POST', 'rest/v2/promql_import/create_mapping_config/');
export const getMappingConfig = request('POST', 'rest/v2/promql_import/get_mapping_config/');
export const deleteMappingConfig = request('POST', 'rest/v2/promql_import/delete_mapping_config/');
export const importGrafanaDashboard = request('POST', 'rest/v2/promql_import/import_grafana_dashboard/');
export const importAlertRule = request('POST', 'rest/v2/promql_import/import_alert_rule/');
export const uploadFile = request('POST', 'rest/v2/promql_import/upload_file/');

export default {
  createMappingConfig,
  getMappingConfig,
  deleteMappingConfig,
  importGrafanaDashboard,
  importAlertRule,
  uploadFile,
};
