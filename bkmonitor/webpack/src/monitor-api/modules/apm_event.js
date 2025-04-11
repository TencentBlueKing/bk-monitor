import { request } from '../base';

export const eventLogs = request('POST', 'apm/event/event/logs/');
export const eventTopK = request('POST', 'apm/event/event/topk/');
export const eventTotal = request('POST', 'apm/event/event/total/');
export const eventViewConfig = request('POST', 'apm/event/event/view_config/');
export const eventTimeSeries = request('POST', 'apm/event/event/time_series/');
export const eventDownloadTopK = request('POST', 'apm/event/event/download_topk/');
export const eventTags = request('POST', 'apm/event/event/tags/');
export const eventTagDetail = request('POST', 'apm/event/event/tag_detail/');
export const eventGetTagConfig = request('POST', 'apm/event/event/get_tag_config/');
export const eventTagStatistics = request('POST', 'apm/event/event/tag_statistics/');
export const eventUpdateTagConfig = request('POST', 'apm/event/event/update_tag_config/');
export const eventStatisticsInfo = request('POST', 'apm/event/event/statistics_info/');
export const eventStatisticsGraph = request('POST', 'apm/event/event/statistics_graph/');

export default {
  eventLogs,
  eventTopK,
  eventTotal,
  eventViewConfig,
  eventTimeSeries,
  eventTags,
  eventDownloadTopK,
  eventTagDetail,
  eventGetTagConfig,
  eventTagStatistics,
  eventUpdateTagConfig,
  eventStatisticsInfo,
  eventStatisticsGraph,
};
