import { request } from '../base';

export const dataTypeBarQuery = request('GET', 'apm/topo/global/bar/');
export const topoView = request('GET', 'apm/topo/global/topo/');

export default {
  dataTypeBarQuery,
  topoView,
};
