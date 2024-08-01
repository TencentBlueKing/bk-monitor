import { request } from '../base';

export const listApplicationServices = request('GET', 'apm/profile_api/query/services/');
export const queryProfileBarGraph = request('POST', 'apm/profile_api/query/services_trace_bar/');
export const queryServicesDetail = request('GET', 'apm/profile_api/query/services_detail/');

export default {
  listApplicationServices,
  queryProfileBarGraph,
  queryServicesDetail,
};
