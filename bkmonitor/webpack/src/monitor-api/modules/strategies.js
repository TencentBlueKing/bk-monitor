import { request } from '../base';

export const getScenarioList = request('GET', 'rest/v2/strategies/get_scenario_list/');
export const noticeVariableList = request('GET', 'rest/v2/strategies/notice_variable_list/');
export const getUnitList = request('GET', 'rest/v2/strategies/get_unit_list/');
export const getUnitInfo = request('GET', 'rest/v2/strategies/get_unit_info/');
export const strategyLabel = request('POST', 'rest/v2/strategies/strategy_label/');
export const strategyLabelList = request('GET', 'rest/v2/strategies/strategy_label_list/');
export const deleteStrategyLabel = request('POST', 'rest/v2/strategies/delete_strategy_label/');
export const fetchItemStatus = request('POST', 'rest/v2/strategies/fetch_item_status/');
export const getTargetDetail = request('POST', 'rest/v2/strategies/get_target_detail/');
export const deleteStrategyConfig = request('POST', 'rest/v2/strategies/delete_strategy_config/');
export const bulkEditStrategy = request('POST', 'rest/v2/strategies/bulk_edit_strategy/');
export const plainStrategyList = request('GET', 'rest/v2/strategies/plain_strategy_list/');
export const getIndexSetList = request('GET', 'rest/v2/strategies/get_index_set_list/');
export const getMetricListV2 = request('POST', 'rest/v2/strategies/v2/get_metric_list/');
export const getStrategyListV2 = request('POST', 'rest/v2/strategies/v2/get_strategy_list/');
export const getStrategyV2 = request('GET', 'rest/v2/strategies/v2/get_strategy/');
export const deleteStrategyV2 = request('POST', 'rest/v2/strategies/v2/delete_strategy/');
export const verifyStrategyName = request('POST', 'rest/v2/strategies/v2/verify_strategy_name/');
export const saveStrategyV2 = request('POST', 'rest/v2/strategies/v2/save_strategy/');
export const updatePartialStrategyV2 = request('POST', 'rest/v2/strategies/v2/update_partial_strategy/');
export const queryConfigToPromql = request('POST', 'rest/v2/strategies/query_config_to_promql/');
export const promqlToQueryConfig = request('POST', 'rest/v2/strategies/promql_to_query_config/');
export const listIntelligentModels = request('GET', 'rest/v2/strategies/list_intelligent_models/');
export const getIntelligentModel = request('GET', 'rest/v2/strategies/get_intelligent_model/');
export const getIntelligentModelTaskStatus = request('GET', 'rest/v2/strategies/get_intelligent_model_task_status/');
export const getIntelligentDetectAccessStatus = request('GET', 'rest/v2/strategies/get_intelligent_detect_access_status/');
export const updateMetricListByBiz = request('POST', 'rest/v2/strategies/update_metric_list_by_biz/');
export const multivariateAnomalyScenes = request('GET', 'rest/v2/strategies/multivariate_anomaly_scenes/');
export const dashboardPanelToQueryConfig = request('POST', 'rest/v2/strategies/dashboard_panel_to_query_config/');
export const getDevopsStrategyList = request('GET', 'rest/v2/strategies/get_devops_strategy_list/');
export const saveStrategySubscribe = request('POST', 'rest/v2/strategies/subscribe/save/');
export const deleteStrategySubscribe = request('POST', 'rest/v2/strategies/subscribe/delete/');
export const listStrategySubscribe = request('GET', 'rest/v2/strategies/subscribe/list/');
export const detailStrategySubscribe = request('GET', 'rest/v2/strategies/subscribe/detail/');
export const bulkSaveStrategySubscribe = request('POST', 'rest/v2/strategies/subscribe/bulk_save/');
export const bulkDeleteStrategySubscribe = request('POST', 'rest/v2/strategies/subscribe/bulk_delete/');

export default {
  getScenarioList,
  noticeVariableList,
  getUnitList,
  getUnitInfo,
  strategyLabel,
  strategyLabelList,
  deleteStrategyLabel,
  fetchItemStatus,
  getTargetDetail,
  deleteStrategyConfig,
  bulkEditStrategy,
  plainStrategyList,
  getIndexSetList,
  getMetricListV2,
  getStrategyListV2,
  getStrategyV2,
  deleteStrategyV2,
  verifyStrategyName,
  saveStrategyV2,
  updatePartialStrategyV2,
  queryConfigToPromql,
  promqlToQueryConfig,
  listIntelligentModels,
  getIntelligentModel,
  getIntelligentModelTaskStatus,
  getIntelligentDetectAccessStatus,
  updateMetricListByBiz,
  multivariateAnomalyScenes,
  dashboardPanelToQueryConfig,
  getDevopsStrategyList,
  saveStrategySubscribe,
  deleteStrategySubscribe,
  listStrategySubscribe,
  detailStrategySubscribe,
  bulkSaveStrategySubscribe,
  bulkDeleteStrategySubscribe,
};
