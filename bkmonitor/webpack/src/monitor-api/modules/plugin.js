import { request } from '../base';

export const dataDogPluginUpload = request('POST', 'rest/v2/collector_plugin/data_dog_plugin_upload/');
export const saveMetric = request('POST', 'rest/v2/collector_plugin/save_metric/');
export const pluginRegister = request('POST', 'rest/v2/collector_plugin/plugin_register/');
export const saveAndReleasePlugin = request('POST', 'rest/v2/collector_plugin/save_and_release_plugin/');
export const getReservedWord = request('GET', 'rest/v2/collector_plugin/get_reserved_word/');
export const pluginUpgradeInfo = request('GET', 'rest/v2/collector_plugin/plugin_upgrade_info/');
export const processCollectorDebug = request('POST', 'rest/v2/collector_plugin/process_collector_debug/');

export default {
  dataDogPluginUpload,
  saveMetric,
  pluginRegister,
  saveAndReleasePlugin,
  getReservedWord,
  pluginUpgradeInfo,
  processCollectorDebug,
};
