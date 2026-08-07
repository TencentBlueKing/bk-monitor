import { request } from '../base';

export const hostPerformanceDetail = request('POST', 'rest/v2/performance/host_performance_detail/');
export const hostTopoNodeDetail = request('POST', 'rest/v2/performance/host_topo_node_detail/');
export const topoNodeProcessStatus = request('POST', 'rest/v2/performance/topo_node_process_status/');
export const hostPerformance = request('GET', 'rest/v2/performance/host_list/');
export const searchHostInfo = request('POST', 'rest/v2/performance/search_host_info/');
export const searchHostMetric = request('POST', 'rest/v2/performance/search_host_metric/');

export const getHostViewsPanels = request('POST', 'rest/v2/scene_view/get_host_views_panels/');
export const getHostMetricGroupPanelOrder = request('POST', 'rest/v2/scene_view/get_host_metric_group_panel_order/');
export const getProcessViewsPanels = request('POST', 'rest/v2/scene_view/get_process_views_panels/');
export const getProcessMetricGroupPanelOrder = request('POST', 'rest/v2/scene_view/get_process_metric_group_panel_order/');

export default {
  hostPerformanceDetail,
  hostTopoNodeDetail,
  topoNodeProcessStatus,
  hostPerformance,
  searchHostInfo,
  searchHostMetric,
  getHostViewsPanels,
  getHostMetricGroupPanelOrder,
  getProcessViewsPanels,
  getProcessMetricGroupPanelOrder,
};
