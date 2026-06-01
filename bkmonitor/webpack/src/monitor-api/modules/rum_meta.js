import { request } from '../base';

export const getMetaConfigInfo = request('POST', 'rum/meta/meta_info/meta_config_info/');
export const listEsClusterGroups = request('GET', 'rum/meta/meta_info/list_cluster_groups/');
export const createApplication = request('POST', 'rum/meta/application/create_application/');
export const checkDuplicateAppName = request('POST', 'rum/meta/application/check_duplicate_app_name/');
export const deleteApplication = request('POST', 'rum/meta/application/delete_application/');
export const startDataSource = request('POST', 'rum/meta/application/start/');
export const stopDataSource = request('POST', 'rum/meta/application/stop/');
export const getApplicationInfoByAppName = request('POST', 'rum/meta/application/application_info_by_app_name/');
export const setupApplication = request('POST', 'rum/meta/application/setup/');
export const getStorageInfo = request('POST', 'rum/meta/application/storage_info/');
export const getIndicesInfo = request('POST', 'rum/meta/application/indices_info/');
export const getDataSampling = request('POST', 'rum/meta/application/data_sampling/');
export const getNoDataStrategyInfo = request('POST', 'rum/meta/application/nodata_strategy_info/');
export const noDataStrategyEnable = request('POST', 'rum/meta/application/nodata_strategy_enable/');
export const noDataStrategyDisable = request('POST', 'rum/meta/application/nodata_strategy_disable/');
export const getDataViewConfig = request('POST', 'rum/meta/application/data_view_config/');
export const listApplication = request('POST', 'rum/meta/application/list_application/');
export const listApplicationAsync = request('POST', 'rum/meta/application/list_application_async/');
export const queryRumTokenInfo = request('POST', 'rum/meta/application/query_rum_token/');
export const storageFieldInfo = request('POST', 'rum/meta/application/storage_field_info/');

export default {
  getMetaConfigInfo,
  listEsClusterGroups,
  createApplication,
  checkDuplicateAppName,
  deleteApplication,
  startDataSource,
  stopDataSource,
  getApplicationInfoByAppName,
  setupApplication,
  getStorageInfo,
  getIndicesInfo,
  getDataSampling,
  getNoDataStrategyInfo,
  noDataStrategyEnable,
  noDataStrategyDisable,
  getDataViewConfig,
  listApplication,
  listApplicationAsync,
  queryRumTokenInfo,
  storageFieldInfo,
};
