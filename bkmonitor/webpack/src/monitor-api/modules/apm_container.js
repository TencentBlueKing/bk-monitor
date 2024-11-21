import { request } from '../base';

export const listServicePods = request('POST', 'apm/container/k8s/list_service_pods/');

export default {
  listServicePods,
};
