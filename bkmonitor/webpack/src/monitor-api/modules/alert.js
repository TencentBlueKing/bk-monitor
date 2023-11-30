import { request } from '../base';

export const listAllowedBiz = request('GET', 'fta/alert/allowed_biz/');
export const listSearchHistory = request('GET', 'fta/alert/search_history/');
export const searchAlert = request('POST', 'fta/alert/alert/search/');
export const exportAlert = request('POST', 'fta/alert/alert/export/');
export const alertDateHistogram = request('POST', 'fta/alert/alert/date_histogram/');
export const listAlertTags = request('POST', 'fta/alert/alert/tags/');
export const alertDetail = request('GET', 'fta/alert/alert/detail/');
export const getExperience = request('GET', 'fta/alert/alert/get_experience/');
export const saveExperience = request('POST', 'fta/alert/alert/save_experience/');
export const deleteExperience = request('POST', 'fta/alert/alert/delete_experience/');
export const listAlertLog = request('POST', 'fta/alert/alert/log/');
export const searchEvent = request('POST', 'fta/alert/event/search/');
export const alertEventCount = request('POST', 'fta/alert/alert/event_count/');
export const alertRelatedInfo = request('POST', 'fta/alert/alert/related_info/');
export const alertExtendFields = request('POST', 'fta/alert/alert/extend_fields/');
export const ackAlert = request('POST', 'fta/alert/alert/ack/');
export const alertGraphQuery = request('POST', 'fta/alert/alert/graph_query/');
export const eventDateHistogram = request('POST', 'fta/alert/event/date_histogram/');
export const searchAction = request('POST', 'fta/alert/action/search/');
export const actionDetail = request('GET', 'fta/alert/action/detail/');
export const subActionDetail = request('GET', 'fta/alert/action/detail/sub_actions/');
export const exportAction = request('POST', 'fta/alert/action/export/');
export const actionDateHistogram = request('POST', 'fta/alert/action/date_histogram/');
export const validateQueryString = request('POST', 'fta/alert/validate_query_string/');
export const strategySnapshot = request('GET', 'fta/alert/strategy_snapshot/');
export const alertTopN = request('POST', 'fta/alert/alert/top_n/');
export const actionTopN = request('POST', 'fta/alert/action/top_n/');
export const eventTopN = request('POST', 'fta/alert/event/top_n/');
export const listIndexByHost = request('POST', 'fta/alert/list_index_by_host/');
export const feedbackAlert = request('POST', 'fta/alert/alert/create_feedback/');
export const listAlertFeedback = request('GET', 'fta/alert/alert/list_feedback/');
export const dimensionDrillDown = request('GET', 'fta/alert/alert/dimension_drill_down/');
export const metricRecommendation = request('GET', 'fta/alert/alert/metric_recommendation/');
export const metricRecommendationFeedback = request('POST', 'fta/alert/alert/metric_recommendation_feedback/');
export const multiAnomalyDetectGraph = request('GET', 'fta/alert/alert/multi_anomaly_detect_graph/');
export const quickAlertShield = request('GET', 'fta/alert/alert/quick_shield/');
export const quickAlertAck = request('GET', 'fta/alert/alert/quick_ack/');

export default {
  listAllowedBiz,
  listSearchHistory,
  searchAlert,
  exportAlert,
  alertDateHistogram,
  listAlertTags,
  alertDetail,
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
  quickAlertShield,
  quickAlertAck
};
