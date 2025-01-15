import { request } from '../base';

export const dataDogPluginUpload = request('POST', 'rest/v2/data_dog_plugin/');
export const saveMetric = request('POST', 'rest/v2/metric_plugin/save/');
export const pluginRegister = request('POST', 'rest/v2/register_plugin/');
export const saveAndReleasePlugin = request('POST', 'rest/v2/save_and_release_plugin/');
export const getReservedWord = request('GET', 'rest/v2/get_reserved_word/');
export const pluginUpgradeInfo = request('GET', 'rest/v2/plugin_upgrade_info/');
export const pluginType = request('GET', 'rest/v2/plugin_type/');

export default {
  dataDogPluginUpload,
  saveMetric,
  pluginRegister,
  saveAndReleasePlugin,
  getReservedWord,
  pluginUpgradeInfo,
  pluginType,
};
