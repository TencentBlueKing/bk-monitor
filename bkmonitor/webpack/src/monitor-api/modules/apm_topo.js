import { request } from '../base';

export const topoView = request('POST', 'apm/topo/topo/topo_view/');

export default {
  topoView,
};
