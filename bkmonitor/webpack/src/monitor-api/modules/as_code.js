import { request } from '../base';

export const importConfig = request('POST', 'rest/v2/as_code/import_config/');
export const exportConfig = request('POST', 'rest/v2/as_code/export_config_json/');
export const exportAllConfigFile = request('GET', 'rest/v2/as_code/export_config/');
export const exportConfigFile = request('POST', 'rest/v2/as_code/export_config_file/');
export const importConfigFile = request('POST', 'rest/v2/as_code/import_config_file/');

export default {
  importConfig,
  exportConfig,
  exportAllConfigFile,
  exportConfigFile,
  importConfigFile,
};
