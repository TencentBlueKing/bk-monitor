import { request } from '../base';

export const dataTypeBarQuery = request('GET', 'apm/topo/global/bar/');
export const topoView = request('GET', 'apm/topo/global/topo/');
export const topoLink = request('GET', 'apm/topo/global/topo/link/');
export const nodeEndpointsTop = request('GET', 'apm/topo/global/topo/node/endpoints/');
export const nodeRelation = request('GET', 'apm/topo/global/relation/');
export const nodeRelationDetail = request('POST', 'apm/topo/global/relation/detail/');

export default {
  dataTypeBarQuery,
  topoView,
  topoLink,
  nodeEndpointsTop,
  nodeRelation,
  nodeRelationDetail,
};
