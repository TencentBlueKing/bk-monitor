import { request } from '../base';

// 声明图表已支持 namespace 与 pod 组合身份，供后端兼容旧前端。
const federationAwareRequest = (method, url) => {
  const handler = request(method, url);
  return (params = {}, options = undefined) => handler({ ...params, supports_federated_charts: true }, options);
};

export const listBcsCluster = request('GET', 'rest/v2/k8s/resources/list_bcs_cluster/');
export const scenarioMetricList = request('GET', 'rest/v2/k8s/resources/scenario_metric_list/');
export const listK8sResources = federationAwareRequest('POST', 'rest/v2/k8s/resources/list_resources/');
export const listK8sResourcesWithoutFederatedCharts = request('POST', 'rest/v2/k8s/resources/list_resources/');
export const getResourceDetail = federationAwareRequest('GET', 'rest/v2/k8s/resources/get_resource_detail/');
export const workloadOverview = federationAwareRequest('GET', 'rest/v2/k8s/resources/workload_overview/');
export const resourceTrend = request('POST', 'rest/v2/k8s/resources/resource_trend/');
export const namespaceWorkloadOverview = request('POST', 'rest/v2/k8s/resources/namespace_workload_overview/');

export default {
  listBcsCluster,
  scenarioMetricList,
  listK8sResources,
  listK8sResourcesWithoutFederatedCharts,
  getResourceDetail,
  workloadOverview,
  resourceTrend,
  namespaceWorkloadOverview,
};
