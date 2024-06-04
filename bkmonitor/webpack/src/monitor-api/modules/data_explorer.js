import { request } from '../base';

export const getGraphQueryConfig = request('POST', 'rest/v2/data_explorer/get_graph_query_config/');
export const getPromqlQueryConfig = request('POST', 'rest/v2/data_explorer/get_promql_query_config/');
export const getEventViewConfig = request('POST', 'rest/v2/data_explorer/get_event_view_config/');
export const getGroupByCount = request('POST', 'rest/v2/data_explorer/get_group_by_count/');

export default {
  getGraphQueryConfig,
  getPromqlQueryConfig,
  getEventViewConfig,
  getGroupByCount,
};
