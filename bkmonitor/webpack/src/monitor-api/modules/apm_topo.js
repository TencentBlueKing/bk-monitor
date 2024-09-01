import { request } from '../base';

export const dataTypeBarQuery = request('GET', 'apm/topo/global/bar/');
export const topoView = request('GET', 'apm/topo/global/topo/');
export const nodeRelation = request('GET', 'apm/topo/global/relation/');
export const nodeRelationDetail = request('POST', 'apm/topo/global/relation/detail/');

export default {
  dataTypeBarQuery,
  topoView,
  nodeRelation,
  nodeRelationDetail,
};
