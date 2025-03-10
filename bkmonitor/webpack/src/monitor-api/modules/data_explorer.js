import { request } from '../base';

export const getGraphQueryConfig = request('POST', 'rest/v2/data_explorer/get_graph_query_config/');
export const getPromqlQueryConfig = request('POST', 'rest/v2/data_explorer/get_promql_query_config/');
export const getEventViewConfig = request('POST', 'rest/v2/data_explorer/get_event_view_config/');
export const getGroupByCount = request('POST', 'rest/v2/data_explorer/get_group_by_count/');
export const eventLogs = request('POST', 'rest/v2/data_explorer/event/logs/');
export const eventTopK = request('POST', 'rest/v2/data_explorer/event/topk/');
export const eventTotal = request('POST', 'rest/v2/data_explorer/event/total/');
export const eventViewConfig = request('POST', 'rest/v2/data_explorer/event/view_config/');
export const eventTimeSeries = request('POST', 'rest/v2/data_explorer/event/time_series/');
export const eventDownloadTopK = request('GET', 'rest/v2/data_explorer/event/download_topk/');

export default {
  getGraphQueryConfig,
  getPromqlQueryConfig,
  getEventViewConfig,
  getGroupByCount,
  eventLogs,
  eventTopK,
  eventTotal,
  eventViewConfig,
  eventTimeSeries,
  eventDownloadTopK,
};
