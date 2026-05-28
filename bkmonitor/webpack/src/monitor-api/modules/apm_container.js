import { request } from '../base';

export const listServicePods = request('POST', 'apm/container/k8s/list_service_pods/');
export const listServiceK8sTargets = request('POST', 'apm/container/k8s/list_service_k8s_targets/');
export const podDetail = request('POST', 'apm/container/k8s/pod_detail/');

export default {
  listServicePods,
  listServiceK8sTargets,
  podDetail,
};
