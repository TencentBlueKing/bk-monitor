import { request } from '../base';

export const listAllowedBiz = request('GET', 'fta/alert/v2/allowed_biz/');
export const listSearchHistory = request('GET', 'fta/alert/v2/search_history/');
export const searchAlert = request('POST', 'fta/alert/v2/alert/search/');
export const exportAlert = request('POST', 'fta/alert/v2/alert/export/');
export const alertDateHistogram = request('POST', 'fta/alert/v2/alert/date_histogram/');
export const listAlertTags = request('POST', 'fta/alert/v2/alert/tags/');
export const getExperience = request('GET', 'fta/alert/v2/alert/get_experience/');
export const saveExperience = request('POST', 'fta/alert/v2/alert/save_experience/');
export const deleteExperience = request('POST', 'fta/alert/v2/alert/delete_experience/');
export const listAlertLog = request('POST', 'fta/alert/v2/alert/log/');
export const searchEvent = request('POST', 'fta/alert/v2/event/search/');
export const alertEventCount = request('POST', 'fta/alert/v2/alert/event_count/');
export const alertRelatedInfo = request('POST', 'fta/alert/v2/alert/related_info/');
export const alertExtendFields = request('POST', 'fta/alert/v2/alert/extend_fields/');
export const ackAlert = request('POST', 'fta/alert/v2/alert/ack/');
export const alertGraphQuery = request('POST', 'fta/alert/v2/alert/graph_query/');
export const eventDateHistogram = request('POST', 'fta/alert/v2/event/date_histogram/');
export const searchAction = request('POST', 'fta/alert/v2/action/search/');
export const actionDetail = request('GET', 'fta/alert/v2/action/detail/');
export const subActionDetail = request('GET', 'fta/alert/v2/action/detail/sub_actions/');
export const exportAction = request('POST', 'fta/alert/v2/action/export/');
export const actionDateHistogram = request('POST', 'fta/alert/v2/action/date_histogram/');
export const validateQueryString = request('POST', 'fta/alert/v2/validate_query_string/');
export const strategySnapshot = request('GET', 'fta/alert/v2/strategy_snapshot/');
export const alertTopN = request('POST', 'fta/alert/v2/alert/top_n/');
export const actionTopN = request('POST', 'fta/alert/v2/action/top_n/');
export const eventTopN = request('POST', 'fta/alert/v2/event/top_n/');
export const listIndexByHost = request('POST', 'fta/alert/v2/list_index_by_host/');
export const feedbackAlert = request('POST', 'fta/alert/v2/alert/create_feedback/');
export const listAlertFeedback = request('GET', 'fta/alert/v2/alert/list_feedback/');
export const dimensionDrillDown = request('GET', 'fta/alert/v2/alert/dimension_drill_down/');
export const metricRecommendation = request('GET', 'fta/alert/v2/alert/metric_recommendation/');
export const metricRecommendationFeedback = request('POST', 'fta/alert/v2/alert/metric_recommendation_feedback/');
export const multiAnomalyDetectGraph = request('GET', 'fta/alert/v2/alert/multi_anomaly_detect_graph/');
export const getFourMetricsStrategy = request('GET', 'fta/alert/v2/alert/get_four_metrics_strategy/');
export const getTmpData = request('GET', 'fta/alert/v2/alert/get_tmp_data/');
export const getFourMetricsData = request('GET', 'fta/alert/v2/alert/get_four_metrics_data/');
export const alertDetail = request('GET', 'fta/alert/v2/alert/detail/');
export const alertEvents = request('POST', 'fta/alert/v2/alert/events/');
export const alertEventTotal = request('GET', 'fta/alert/v2/alert/event_total/');
export const alertEventTs = request('POST', 'fta/alert/v2/alert/event_ts/');
export const alertEventTagDetail = request('POST', 'fta/alert/v2/alert/event_tag_detail/');
export const alertK8sScenarioList = request('GET', 'fta/alert/v2/alert/k8s_scenario_list/');
export const alertK8sMetricList = request('GET', 'fta/alert/v2/alert/k8s_metric_list/');
export const alertK8sTarget = request('GET', 'fta/alert/v2/alert/k8s_target/');
export const alertHostTarget = request('GET', 'fta/alert/v2/alert/host_target/');
export const alertTraces = request('POST', 'fta/alert/v2/alert/traces/');
export const alertLogRelationList = request('GET', 'fta/alert/v2/alert/log_relation_list/');
export const quickAlertShield = request('GET', 'fta/alert/v2/alert/quick_shield/');
export const quickAlertAck = request('GET', 'fta/alert/v2/alert/quick_ack/');

export default {
  listAllowedBiz,
  listSearchHistory,
  searchAlert,
  exportAlert,
  alertDateHistogram,
  listAlertTags,
  getExperience,
  saveExperience,
  deleteExperience,
  listAlertLog,
  searchEvent,
  alertEventCount,
  alertRelatedInfo,
  alertExtendFields,
  ackAlert,
  alertGraphQuery,
  eventDateHistogram,
  searchAction,
  actionDetail,
  subActionDetail,
  exportAction,
  actionDateHistogram,
  validateQueryString,
  strategySnapshot,
  alertTopN,
  actionTopN,
  eventTopN,
  listIndexByHost,
  feedbackAlert,
  listAlertFeedback,
  dimensionDrillDown,
  metricRecommendation,
  metricRecommendationFeedback,
  multiAnomalyDetectGraph,
  getFourMetricsStrategy,
  getTmpData,
  getFourMetricsData,
  alertDetail,
  alertEvents,
  alertEventTotal,
  alertEventTs,
  alertEventTagDetail,
  alertK8sScenarioList,
  alertK8sMetricList,
  alertK8sTarget,
  alertHostTarget,
  alertTraces,
  alertLogRelationList,
  quickAlertShield,
  quickAlertAck,
};
