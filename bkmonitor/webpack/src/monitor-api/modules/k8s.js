import { request } from '../base';

export const listBcsCluster = request('GET', 'rest/v2/k8s/resources/list_bcs_cluster/');
export const scenarioMetricList = request('GET', 'rest/v2/k8s/resources/scenario_metric_list/');
export const listK8sResources = request('POST', 'rest/v2/k8s/resources/list_resources/');
export const getResourceDetail = request('GET', 'rest/v2/k8s/resources/get_resource_detail/');
export const workloadOverview = request('GET', 'rest/v2/k8s/resources/workload_overview/');
export const resourceTrend = request('POST', 'rest/v2/k8s/resources/resource_trend/');

export default {
  listBcsCluster,
  scenarioMetricList,
  listK8sResources,
  getResourceDetail,
  workloadOverview,
  resourceTrend,
};
